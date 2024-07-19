import streamlit as st
import xml.etree.ElementTree as ET

def extract_podcast_info(xml_string):
    # Remove any leading whitespace and find the start of the XML declaration
    xml_string = xml_string.lstrip()
    start_index = xml_string.find('<?xml')
    if start_index != -1:
        xml_string = xml_string[start_index:]
    else:
        st.warning("XML declaration not found. This might cause issues.")
    
    # Parse the XML string
    try:
        root = ET.fromstring(xml_string)
    except ET.ParseError as e:
        st.error(f"Error parsing XML: {e}")
        return None
    
    # Find all item elements
    items = root.findall(".//item")
    st.info(f"Found {len(items)} item elements in the XML")
    
    # Extract podcast information
    podcast_info = []
    for i, item in enumerate(items):
        st.write(f"Processing item {i+1}:")
        title_elem = item.find("title")
        title = title_elem.text if title_elem is not None else "No title"
        st.write(f"  Title: {title}")
        
        enclosure = item.find("enclosure")
        if enclosure is not None:
            st.write("  Enclosure found")
            mp3_url = enclosure.get('url')
            st.write(f"  URL in enclosure: {mp3_url}")
            if mp3_url and mp3_url.endswith('.mp3'):
                mp3_url = mp3_url.split('?')[0]  # Remove query parameters
                podcast_info.append({
                    "title": title,
                    "mp3_url": mp3_url
                })
                st.write("  Valid MP3 URL found and added to results")
            else:
                st.write("  URL does not end with .mp3 or is empty")
        else:
            st.write("  No enclosure found in this item")
    
    return podcast_info

st.title('Podcast MP3 Link Extractor')

# Text area for manual input
xml_input = st.text_area("Paste your XML here:", height=300)

if xml_input:
    st.write("Processing XML input...")
    podcast_info = extract_podcast_info(xml_input)
    if podcast_info is not None:
        if podcast_info:
            st.success(f"Found {len(podcast_info)} podcast episode(s) with MP3 links:")
            for info in podcast_info:
                st.write(f"Title: {info['title']}")
                st.write(f"MP3 URL: {info['mp3_url']}")
                st.write("---")
        else:
            st.warning("No podcast episodes with MP3 links found in the provided XML.")
    st.write("XML processing complete.")
else:
    st.info("Please paste XML content to extract podcast information and MP3 links.")
