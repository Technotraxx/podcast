import streamlit as st
import xml.etree.ElementTree as ET
import requests
import os
import tempfile
from groq import Groq
from datetime import datetime
import json
from pathlib import Path
import hashlib
from pydub import AudioSegment
import math
import io
import concurrent.futures
import time

# Constants
MAX_CHUNK_SIZE = 24 * 1024 * 1024  # 24MB to be safe
CHUNK_OVERLAP_SEC = 5  # Overlap between chunks in seconds
CACHE_DIR = Path("./cache")
CACHE_DIR.mkdir(exist_ok=True)
MAX_CACHE_AGE_DAYS = 7
MAX_CACHE_SIZE_MB = 1000

# Initialize session state
if 'transcriptions' not in st.session_state:
    st.session_state.transcriptions = {}
if 'language' not in st.session_state:
    st.session_state.language = 'de'

# Configure the page
st.set_page_config(
    page_title="Podcast Transcriber Pro",
    page_icon="🎙️",
    layout="wide"
)

# Initialize Groq client
@st.cache_resource
def get_groq_client():
    return Groq(api_key=st.secrets["GROQ_API_KEY"])

client = get_groq_client()

def cleanup_old_cache(max_age_days=MAX_CACHE_AGE_DAYS):
    """Remove cache files older than max_age_days"""
    now = datetime.now()
    for cache_file in CACHE_DIR.glob("*.json"):
        try:
            with cache_file.open() as f:
                data = json.load(f)
                timestamp = datetime.fromisoformat(data['timestamp'])
                if (now - timestamp).days > max_age_days:
                    cache_file.unlink()
        except (json.JSONDecodeError, KeyError, ValueError):
            cache_file.unlink()  # Remove corrupted cache files

def check_cache_size(max_size_mb=MAX_CACHE_SIZE_MB):
    """Check if cache directory exceeds max size"""
    total_size = sum(f.stat().st_size for f in CACHE_DIR.glob("*.json")) / (1024 * 1024)
    return total_size <= max_size_mb

def get_cache_key(url):
    """Generate a unique cache key for a URL"""
    return hashlib.md5(url.encode()).hexdigest()

class AudioChunker:
    def __init__(self, max_size_bytes=MAX_CHUNK_SIZE, overlap_sec=CHUNK_OVERLAP_SEC):
        self.max_size_bytes = max_size_bytes
        self.overlap_sec = overlap_sec

    def get_chunk_size_ms(self, audio_segment):
        """Calculate chunk size in milliseconds based on file size and duration"""
        bytes_per_ms = len(audio_segment.raw_data) / len(audio_segment)
        max_ms = self.max_size_bytes / bytes_per_ms
        return int(max_ms)

    def chunk_audio(self, audio_data):
        """Split audio into overlapping chunks"""
        # Load audio from binary data
        audio = AudioSegment.from_mp3(io.BytesIO(audio_data))
        
        # Calculate chunk parameters
        chunk_size_ms = self.get_chunk_size_ms(audio)
        overlap_ms = self.overlap_sec * 1000
        
        chunks = []
        start = 0
        
        while start < len(audio):
            end = start + chunk_size_ms
            
            # Extract chunk with overlap
            chunk = audio[start:end]
            
            # Convert chunk to MP3 bytes
            chunk_buffer = io.BytesIO()
            chunk.export(chunk_buffer, format="mp3")
            chunks.append(chunk_buffer.getvalue())
            
            # Move to next chunk, accounting for overlap
            start = end - overlap_ms
        
        return chunks

def download_mp3_with_progress(url):
    """Download MP3 with progress tracking"""
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        progress_bar = st.progress(0)
        progress_text = st.empty()
        
        chunks = []
        downloaded_size = 0
        
        for chunk in response.iter_content(chunk_size=1024*1024):
            chunks.append(chunk)
            downloaded_size += len(chunk)
            
            if total_size:
                progress = (downloaded_size / total_size)
                progress_bar.progress(progress)
                progress_text.text(f"Downloaded: {downloaded_size//(1024*1024)}MB / {total_size//(1024*1024)}MB")
        
        progress_bar.empty()
        progress_text.empty()
        
        return b''.join(chunks)
    except requests.RequestException as e:
        st.error(f"Failed to download audio: {str(e)}")
        return None

# Cache file operations helper
def safe_write_cache(cache_file: Path, data: dict):
    """Safely write data to cache file"""
    try:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        with cache_file.open('w') as f:
            json.dump(data, f)
        return True
    except Exception as e:
        st.error(f"Failed to write cache: {str(e)}")
        return False

def transcribe_chunk(chunk_data, language='de'):
    """Transcribe a single audio chunk"""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as temp_file:
        temp_file.write(chunk_data)
        temp_file_path = temp_file.name

    try:
        with open(temp_file_path, "rb") as file:
            transcription = client.audio.transcriptions.create(
                file=(os.path.basename(temp_file_path), file),
                model="whisper-large-v3",
                response_format="text",
                language=language,
                temperature=0.0
            )
        return transcription
    except Exception as e:
        st.error(f"Chunk transcription failed: {str(e)}")
        return None
    finally:
        os.unlink(temp_file_path)

def process_large_audio(audio_data, language='de'):
    """Process large audio files by chunking and transcribing"""
    chunker = AudioChunker()
    chunks = chunker.chunk_audio(audio_data)
    
    # Create progress tracking
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    transcriptions = []
    failed_chunks = []
    
    # Process chunks with progress tracking
    for i, chunk in enumerate(chunks):
        status_text.text(f"Processing chunk {i+1} of {len(chunks)}...")
        progress_bar.progress(i / len(chunks))
        
        try:
            transcription = transcribe_chunk(chunk, language)
            if transcription:
                transcriptions.append(transcription)
            else:
                failed_chunks.append(i)
        except Exception as e:
            failed_chunks.append(i)
            st.error(f"Chunk {i} failed: {str(e)}")
        
        # Small delay to avoid rate limiting
        time.sleep(1)
    
    progress_bar.progress(1.0)
    status_text.empty()
    
    if failed_chunks:
        st.warning(f"Some chunks failed: {failed_chunks}")
    
    # Combine transcriptions
    final_text = transcriptions[0] if transcriptions else ""
    for i in range(1, len(transcriptions)):
    final_text = merge_overlapping_text(final_text, transcriptions[i])
    return final_text

def merge_overlapping_text(text1, text2, min_overlap=10):
    """Merge two texts by finding overlapping content"""
    if not text1 or not text2:
        return text1 or text2
    
    # Find the longest common substring at the end of text1 and start of text2
    words1 = text1.split()
    words2 = text2.split()
    
    max_overlap = min(len(words1), len(words2))
    best_overlap = ""
    
    for i in range(min_overlap, max_overlap + 1):
        suffix = " ".join(words1[-i:])
        prefix = " ".join(words2[:i])
        
        if suffix == prefix:
            best_overlap = suffix
            break
    
    if best_overlap:
        # Merge texts using the overlapping portion
        overlap_idx = text2.find(best_overlap)
        if overlap_idx != -1:
            return text1 + text2[overlap_idx + len(best_overlap):]
    
    return text1 + " " + text2

def summarize_long_transcript(transcript, max_tokens=32000):
    """Summarize long transcripts by breaking them into chunks"""
    words = transcript.split()
    chunk_size = max_tokens // 2  # Leave room for system message and response
    
    # Split into chunks of roughly equal size
    chunks = [" ".join(words[i:i + chunk_size]) 
             for i in range(0, len(words), chunk_size)]
    
    summaries = []
    
    for i, chunk in enumerate(chunks):
        try:
            response = client.chat.completions.create(
                model="mixtral-8x7b-32768",
                messages=[
                    {"role": "system", "content": "Generate a concise summary of the following podcast transcript chunk."},
                    {"role": "user", "content": chunk}
                ],
                temperature=0.3,
                max_tokens=500
            )
            summaries.append(response.choices[0].message.content)
        except Exception as e:
            st.error(f"Summary generation failed for chunk {i+1}: {str(e)}")
    
    # If we have multiple summaries, combine them
    if len(summaries) > 1:
        try:
            final_summary = client.chat.completions.create(
                model="mixtral-8x7b-32768",
                messages=[
                    {"role": "system", "content": "Combine these summaries into a coherent final summary:"},
                    {"role": "user", "content": "\n\n".join(summaries)}
                ],
                temperature=0.3,
                max_tokens=500
            ).choices[0].message.content
        except Exception as e:
            st.error(f"Final summary generation failed: {str(e)}")
            final_summary = "\n\n".join(summaries)
    else:
        final_summary = summaries[0] if summaries else ""
    
    return final_summary

def fetch_rss_content(url):
    """Fetch and cache RSS content"""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        st.error(f"Failed to fetch RSS feed: {str(e)}")
        return None

def extract_podcast_info(xml_string):
    """Extract and validate podcast information from XML"""
    try:
        root = ET.fromstring(xml_string)
        channel = root.find('channel')
        
        # Extract podcast metadata
        podcast_metadata = {
            'title': channel.find('title').text if channel.find('title') is not None else "Unknown Podcast",
            'description': channel.find('description').text if channel.find('description') is not None else "",
            'language': channel.find('language').text if channel.find('language') is not None else "de"
        }
        
        items = root.findall(".//item")
        podcast_info = []
        
        for item in items:
            episode = {}
            
            # Extract basic information
            for tag in ['title', 'description', 'pubDate']:
                elem = item.find(tag)
                episode[tag] = elem.text if elem is not None else ""
            
            # Extract MP3 URL
            enclosure = item.find("enclosure")
            if enclosure is not None:
                mp3_url = enclosure.get('url')
                if mp3_url and '.mp3' in mp3_url:
                    episode['mp3_url'] = mp3_url.split('.mp3')[0] + '.mp3'
                    podcast_info.append(episode)
        
        return podcast_metadata, podcast_info
    except ET.ParseError as e:
        st.error(f"Invalid XML format: {str(e)}")
        return None, None
    except Exception as e:
        st.error(f"Error processing podcast data: {str(e)}")
        return None, None

def main():
    st.title('🎙️ Podcast Transcriber Pro')
    st.markdown("Transform your favorite podcasts into searchable text")
    
    # Settings sidebar
    with st.sidebar:
        st.header("Settings")
        st.session_state.language = st.selectbox(
            "Transcription Language",
            options=['de', 'en', 'fr', 'es', 'it'],
            format_func=lambda x: {'de': 'German', 'en': 'English', 'fr': 'French', 'es': 'Spanish', 'it': 'Italian'}[x]
        )
        
        st.markdown("---")
        st.markdown("### About")
        st.markdown("This app helps you transcribe podcast episodes and generate summaries.")
    
    # Cleanup old cache files
    cleanup_old_cache()
    
    # Check cache size
    if not check_cache_size():
        st.warning("Cache size limit exceeded. Cleaning up old files...")
        cleanup_old_cache(max_age_days=1)  # More aggressive cleanup
    
    # Main interface
    input_method = st.radio(
        "Choose input method:",
        ("Enter RSS URL 🔗", "Paste XML 📝"),
        help="Select how you want to input your podcast data"
    )

    if input_method == "Enter RSS URL 🔗":
        rss_url = st.text_input(
            "Enter RSS URL:",
            placeholder="https://example.com/feed.xml"
        )
        
        if rss_url:
            with st.spinner("Fetching podcast feed..."):
                xml_content = fetch_rss_content(rss_url)
                if xml_content:
                    st.success("RSS feed fetched successfully!")
                    with st.expander("View Raw XML"):
                        st.code(xml_content, language="xml")
                    xml_input = xml_content
                else:
                    xml_input = None
        else:
            xml_input = None
    else:
        xml_input = st.text_area(
            "Paste your XML here:",
            height=300,
            help="Paste the raw XML content of your podcast feed"
        )

    if xml_input:
        podcast_metadata, podcast_info = extract_podcast_info(xml_input)
        
        if podcast_metadata and podcast_info:
            st.header(podcast_metadata['title'])
            st.markdown(podcast_metadata['description'])
            
            st.success(f"Found {len(podcast_info)} podcast episode(s)")
            
            # Display episodes in columns
            for idx, info in enumerate(podcast_info):
                with st.container():
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        st.markdown(f"### {info['title']}")
                        st.markdown(f"*Published: {info['pubDate']}*")
                        
                        with st.expander("Show Description"):
                            st.markdown(info['description'])
                    
                    with col2:
                        st.markdown(f"[Download MP3]({info['mp3_url']})")
                        
                        if st.button(f"Transcribe Episode", key=f"transcribe_{idx}"):
                            cache_key = get_cache_key(info['mp3_url'])
                            cache_file = CACHE_DIR / f"{cache_key}.json"
                            
                            # Initialize variables
                            transcription = None
                            summary = None
                            
                            if cache_file.exists():
                                with cache_file.open() as f:
                                    try:
                                        cached_data = json.load(f)
                                        transcription = cached_data.get('transcription')
                                        summary = cached_data.get('summary')
                                        st.success("Loaded transcription from cache!")
                                    except json.JSONDecodeError:
                                        st.warning("Cache file corrupted. Reprocessing audio...")
                                        cache_file.unlink()
                            
                            # If not in cache or cache loading failed, process the audio
                            if not transcription:
                                with st.spinner('Downloading audio...'):
                                    audio_content = download_mp3_with_progress(info['mp3_url'])
                                    
                                if audio_content:
                                    file_size = len(audio_content)
                                    
                                    if file_size > MAX_CHUNK_SIZE:
                                        st.info(f"Large file detected ({file_size//(1024*1024)}MB). Processing in chunks...")
                                        transcription = process_large_audio(
                                            audio_content,
                                            language=st.session_state.language
                                        )
                                    else:
                                        with st.spinner('Transcribing audio...'):
                                            transcription = transcribe_chunk(
                                                audio_content,
                                                language=st.session_state.language
                                            )
                                    
                                    if transcription:
                                        # Generate summary if not already in cache
                                        if not summary:
                                            with st.spinner('Generating summary...'):
                                                summary = summarize_long_transcript(transcription)
                                        
                                        # Cache both transcription and summary
                                        cache_data = {
                                            'transcription': transcription,
                                            'summary': summary,
                                            'timestamp': datetime.now().isoformat()
                                        }
                                        with cache_file.open('w') as f:
                                            json.dump(cache_data, f)
                                        
                                        st.success("Processing complete!")
                                    else:
                                        st.error("Transcription failed.")
                                else:
                                    st.error("Failed to download audio.")
                            
                            # Display results (whether from cache or new processing)
                            if transcription:
                                tab1, tab2 = st.tabs(["Full Transcription", "Summary"])
                                
                                with tab1:
                                    st.text_area(
                                        "Full Transcription:",
                                        value=transcription,
                                        height=400
                                    )
                                    
                                    # Download buttons
                                    col1, col2 = st.columns(2)
                                    with col1:
                                        st.download_button(
                                            "Download Transcription (TXT)",
                                            transcription,
                                            file_name=f"{info['title']}_transcript.txt"
                                        )
                                    with col2:
                                        st.download_button(
                                            "Download Transcription (JSON)",
                                            json.dumps({
                                                'title': info['title'],
                                                'date': info['pubDate'],
                                                'transcription': transcription,
                                                'summary': summary
                                            }, indent=2),
                                            file_name=f"{info['title']}_transcript.json"
                                        )
                                
                                with tab2:
                                    if summary:
                                        st.markdown("### Episode Summary")
                                        st.markdown(summary)
                                    else:
                                        with st.spinner('Generating summary...'):
                                            summary = summarize_long_transcript(transcription)
                                            if summary:
                                                st.markdown("### Episode Summary")
                                                st.markdown(summary)
                                                # Update cache with new summary
                                                cache_data = {
                                                    'transcription': transcription,
                                                    'summary': summary,
                                                    'timestamp': datetime.now().isoformat()
                                                }
                                                with cache_file.open('w') as f:
                                                    json.dump(cache_data, f)
                                            else:
                                                st.warning("Summary generation failed.")
                    
                    st.markdown("---")

if __name__ == "__main__":
    main()
