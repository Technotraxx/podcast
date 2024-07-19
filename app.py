import streamlit as st
import xml.etree.ElementTree as ET
import requests
import os
import tempfile
from groq import Groq

# Stellen Sie sicher, dass Sie den API-Schlüssel als Streamlit Secret gespeichert haben
# und rufen Sie ihn wie folgt ab:
groq_api_key = st.secrets["GROQ_API_KEY"]

client = Groq(api_key=groq_api_key)

def fetch_rss_content(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        st.error(f"Error fetching RSS feed: {e}")
        return None

def extract_podcast_info(xml_string):
    try:
        root = ET.fromstring(xml_string)
    except ET.ParseError as e:
        st.error(f"Error parsing XML: {e}")
        return None
    
    items = root.findall(".//item")
    
    podcast_info = []
    for item in items:
        title_elem = item.find("title")
        title = title_elem.text if title_elem is not None else "No title"
        
        enclosure = item.find("enclosure")
        if enclosure is not None:
            mp3_url = enclosure.get('url')
            if mp3_url and '.mp3' in mp3_url:
                mp3_url = mp3_url.split('.mp3')[0] + '.mp3'  # Remove everything after .mp3
                podcast_info.append({
                    "title": title,
                    "mp3_url": mp3_url
                })
    
    return podcast_info

def download_mp3(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.content
    except requests.RequestException as e:
        st.error(f"Error downloading MP3: {e}")
        return None

def transcribe_audio(audio_content):
    with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as temp_file:
        temp_file.write(audio_content)
        temp_file_path = temp_file.name

    try:
        with open(temp_file_path, "rb") as file:
            transcription = client.audio.transcriptions.create(
                file=(os.path.basename(temp_file_path), file),
                model="whisper-large-v3",
                response_format="text",
                language="de",  # Angepasst für deutsche Podcasts
                temperature=0.0
            )
        # Die API gibt direkt den transkribierten Text zurück, nicht ein Objekt
        return transcription
    except Exception as e:
        st.error(f"Error during transcription: {e}")
        return None
    finally:
        os.unlink(temp_file_path)

st.title('Podcast MP3 Link Extractor and Transcriber')

input_method = st.radio("Choose input method:", ("Paste XML", "Enter RSS URL"))

if input_method == "Enter RSS URL":
    rss_url = st.text_input("Enter RSS URL:")
    if rss_url:
        xml_content = fetch_rss_content(rss_url)
        if xml_content:
            st.text_area("Fetched XML content:", value=xml_content, height=300)
            xml_input = xml_content
        else:
            xml_input = None
    else:
        xml_input = None
else:
    xml_input = st.text_area("Paste your XML here:", height=300)

if xml_input:
    podcast_info = extract_podcast_info(xml_input)
    if podcast_info is not None:
        if podcast_info:
            st.success(f"Found {len(podcast_info)} podcast episode(s) with MP3 links:")
            for info in podcast_info:
                st.markdown(f"**{info['title']}**")
                st.markdown(f"[Download MP3]({info['mp3_url']})")
                
                if st.button(f"Transcribe: {info['title'][:30]}..."):
                    with st.spinner('Downloading and transcribing audio...'):
                        audio_content = download_mp3(info['mp3_url'])
                        if audio_content:
                            transcription = transcribe_audio(audio_content)
                            if transcription:
                                st.success("Transcription complete!")
                                st.text_area("Transcription:", value=transcription, height=200)
                            else:
                                st.error("Transcription failed.")
                        else:
                            st.error("Failed to download audio.")
                
                st.write("---")
        else:
            st.warning("No podcast episodes with MP3 links found in the provided XML.")
elif input_method == "Paste XML":
    st.info("Please paste XML content to extract podcast information and MP3 links.")
