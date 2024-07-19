import streamlit as st
import xml.etree.ElementTree as ET

def extract_mp3_links(xml_string):
    # Remove any leading whitespace and find the start of the XML declaration
    xml_string = xml_string.lstrip()
    start_index = xml_string.find('<?xml')
    if start_index != -1:
        xml_string = xml_string[start_index:]
    
    # Parse the XML string
    root = ET.fromstring(xml_string)
    
    # Find all enclosure elements
    enclosures = root.findall(".//enclosure")
    
    # Extract the MP3 links
    mp3_links = []
    for enclosure in enclosures:
        url = enclosure.get('url')
        if url and url.endswith('.mp3'):
            mp3_links.append(url.split('?')[0])  # Remove query parameters
    
    return mp3_links

st.title('MP3 Link Extractor from XML')

# File uploader
uploaded_file = st.file_uploader("Choose a TXT file containing XML", type="txt")

# Text area for manual input
xml_input = st.text_area("Or paste your XML here:", height=300)

if uploaded_file is not None:
    # To read file as string:
    xml_string = uploaded_file.getvalue().decode("utf-8")
elif xml_input:
    xml_string = xml_input
else:
    xml_string = None

if xml_string:
    try:
        links = extract_mp3_links(xml_string)
        if links:
            st.success(f"Found {len(links)} MP3 link(s):")
            for link in links:
                st.write(link)
        else:
            st.warning("No MP3 links found in the provided XML.")
    except ET.ParseError as e:
        st.error(f"Error parsing XML: {e}")
        st.text("First 100 characters of XML string:")
        st.code(xml_string[:100])
else:
    st.info("Please upload a TXT file containing XML or paste XML content to extract MP3 links.")
