import streamlit as st
import xml.etree.ElementTree as ET

def extract_podcast_info(xml_string):
    xml_string = xml_string.lstrip()
    start_index = xml_string.find('<?xml')
    if start_index != -1:
        xml_string = xml_string[start_index:]
    else:
        st.warning("XML declaration not found. This might cause issues.")
    
    try:
        root = ET.fromstring(xml_string)
    except ET.ParseError as e:
        st.error(f"Error parsing XML: {e}")
        return None
    
    items = root.findall(".//item")
    st.info(f"Found {len(items)} item elements in the XML")
    
    podcast_info = []
    for i, item in enumerate(items):
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


def get_binary_file_downloader_html(bin_file, file_label='File'):
    with open(bin_file, 'rb') as f:
        data = f.read()
    bin_str = base64.b64encode(data).decode()
    href = f'<a href="data:application/octet-stream;base64,{bin_str}" download="{os.path.basename(bin_file)}">Download {file_label}</a>'
    return href

def download_mp3(url, filename):
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raises an HTTPError if the HTTP request returned an unsuccessful status code
        
        with open(filename, 'wb') as file:
            file.write(response.content)
        
        return True
    except requests.RequestException as e:
        st.error(f"Error downloading file: {e}")
        return False

st.title('Podcast MP3 Link Extractor and Downloader')

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
                
                # Create a unique filename for each episode
                filename = f"{info['title'].replace(' ', '_')}.mp3"
                
                # Download button
                if st.button(f"Download {info['title']}"):
                    with st.spinner('Downloading...'):
                        if download_mp3(info['mp3_url'], filename):
                            st.success(f"Downloaded: {filename}")
                            st.markdown(get_binary_file_downloader_html(filename, 'MP3'), unsafe_allow_html=True)
                        else:
                            st.error("Download failed. Please try again.")
                
                st.write("---")
        else:
            st.warning("No podcast episodes with MP3 links found in the provided XML.")
    st.write("XML processing complete.")
else:
    st.info("Please paste XML content to extract podcast information and MP3 links.")

# Clean up downloaded files
for file in os.listdir():
    if file.endswith(".mp3"):
        os.remove(file)
