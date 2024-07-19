import streamlit as st
import xml.etree.ElementTree as ET
import requests

def fetch_rss_content(url):
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raises an HTTPError for bad responses
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

st.title('Podcast MP3 Link Extractor')

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
                st.write("---")
        else:
            st.warning("No podcast episodes with MP3 links found in the provided XML.")
elif input_method == "Paste XML":
    st.info("Please paste XML content to extract podcast information and MP3 links.")
