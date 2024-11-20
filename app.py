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
import time

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

# Custom CSS
st.markdown("""
    <style>
    .stProgress > div > div > div > div {
        background-color: #1f77b4;
    }
    .success-message {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #d4edda;
        color: #155724;
        margin: 1rem 0;
    }
    </style>
    """, unsafe_allow_html=True)

# Initialize Groq client
@st.cache_resource
def get_groq_client():
    return Groq(api_key=st.secrets["GROQ_API_KEY"])

client = get_groq_client()

# Cache directory setup
CACHE_DIR = Path("./cache")
CACHE_DIR.mkdir(exist_ok=True)

def get_cache_key(url):
    """Generate a unique cache key for a URL"""
    return hashlib.md5(url.encode()).hexdigest()

@st.cache_data(ttl=3600)  # Cache for 1 hour
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

def download_mp3_with_progress(url):
    """Download MP3 with progress tracking"""
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        # Get file size
        total_size = int(response.headers.get('content-length', 0))
        
        # Create progress bar
        progress_bar = st.progress(0)
        progress_text = st.empty()
        
        # Download with progress tracking
        chunks = []
        downloaded_size = 0
        
        for chunk in response.iter_content(chunk_size=1024*1024):  # 1MB chunks
            chunks.append(chunk)
            downloaded_size += len(chunk)
            
            # Update progress
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

@st.cache_data
def transcribe_audio(audio_content, language='de'):
    """Transcribe audio with caching"""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as temp_file:
        temp_file.write(audio_content)
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
        st.error(f"Transcription failed: {str(e)}")
        return None
    finally:
        os.unlink(temp_file_path)

def summarize_transcript(transcript):
    """Generate a summary of the transcript"""
    try:
        response = client.chat.completions.create(
            model="mixtral-8x7b-32768",
            messages=[
                {"role": "system", "content": "Generate a concise summary of the following podcast transcript."},
                {"role": "user", "content": transcript}
            ],
            temperature=0.3,
            max_tokens=150
        )
        return response.choices[0].message.content
    except Exception as e:
        st.error(f"Summary generation failed: {str(e)}")
        return None

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
                            
                            # Check cache first
                            cache_file = CACHE_DIR / f"{cache_key}.json"
                            if cache_file.exists():
                                with cache_file.open() as f:
                                    cached_data = json.load(f)
                                    transcription = cached_data['transcription']
                                    st.success("Loaded transcription from cache!")
                            else:
                                with st.spinner('Downloading audio...'):
                                    audio_content = download_mp3_with_progress(info['mp3_url'])
                                    
                                if audio_content:
                                    with st.spinner('Transcribing audio...'):
                                        transcription = transcribe_audio(
                                            audio_content,
                                            language=st.session_state.language
                                        )
                                        
                                        if transcription:
                                            # Cache the transcription
                                            cache_data = {
                                                'transcription': transcription,
                                                'timestamp': datetime.now().isoformat()
                                            }
                                            with cache_file.open('w') as f:
                                                json.dump(cache_data, f)
                                        
                                            # Generate summary
                                            with st.spinner('Generating summary...'):
                                                summary = summarize_transcript(transcription)
                                            
                                            # Display results
                                            st.success("Processing complete!")
                                            
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
                                                            'transcription': transcription
                                                        }, indent=2),
                                                        file_name=f"{info['title']}_transcript.json"
                                                    )
                                            
                                            with tab2:
                                                if summary:
                                                    st.markdown("### Episode Summary")
                                                    st.markdown(summary)
                                                else:
                                                    st.warning("Summary generation failed.")
                                        else:
                                            st.error("Transcription failed.")
                                else:
                                    st.error("Failed to download audio.")
                    
                    st.markdown("---")

if __name__ == "__main__":
    main()
