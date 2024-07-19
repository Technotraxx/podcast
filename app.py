import streamlit as st
import xml.etree.ElementTree as ET

def extract_podcast_info(xml_string):
    # Remove any leading whitespace and find the start of the XML declaration
    xml_string = xml_string.lstrip()
    start_index = xml_string.find('<?xml')
    if start_index != -1:
        xml_string = xml_string[start_index:]
    
    # Parse the XML string
    root = ET.fromstring(xml_string)
    
    # Find all item elements
    items = root.findall(".//item")
    
    # Extract podcast information
    podcast_info = []
    for item in items:
        title = item.find("title").text if item.find("title") is not None else "No title"
        enclosure = item.find("enclosure")
        if enclosure is not None:
            mp3_url = enclosure.get('url')
            if mp3_url and mp3_url.endswith('.mp3'):
                mp3_url = mp3_url.split('?')[0]  # Remove query parameters
                podcast_info.append({
                    "title": title,
                    "mp3_url": mp3_url
                })
    
    return podcast_info

st.title('Podcast MP3 Link Extractor')

# Text area for manual input
xml_input = st.text_area("Paste your XML here:", height=300)

if xml_input:
    try:
        podcast_info = extract_podcast_info(xml_input)
        if podcast_info:
            st.success(f"Found {len(podcast_info)} podcast episode(s) with MP3 links:")
            for info in podcast_info:
                st.write(f"Title: {info['title']}")
                st.write(f"MP3 URL: {info['mp3_url']}")
                st.write("---")
        else:
            st.warning("No podcast episodes with MP3 links found in the provided XML.")
    except ET.ParseError as e:
        st.error(f"Error parsing XML: {e}")
        st.text("First 100 characters of XML string:")
        st.code(xml_input[:100])
else:
    st.info("Please paste XML content to extract podcast information and MP3 links.")
