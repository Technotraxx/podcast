import streamlit as st
import yt_dlp
import os
from pydub import AudioSegment

def download_and_convert(url):
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': 'temp_audio.%(ext)s'
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    
    # Convert to MP3 if necessary
    if not os.path.exists('temp_audio.mp3'):
        audio = AudioSegment.from_file('temp_audio.webm', format="webm")
        audio.export('temp_audio.mp3', format="mp3")
        os.remove('temp_audio.webm')
    
    return 'temp_audio.mp3'

st.title('YouTube to MP3 Converter')

url = st.text_input('Enter YouTube URL:')
if st.button('Convert to MP3'):
    if url:
        with st.spinner('Converting...'):
            try:
                output_file = download_and_convert(url)
                st.success('Conversion complete!')
                
                with open(output_file, 'rb') as f:
                    st.download_button('Download MP3', f, file_name='audio.mp3', mime='audio/mpeg')
                
                os.remove(output_file)
            except Exception as e:
                st.error(f'An error occurred: {str(e)}')
    else:
        st.warning('Please enter a YouTube URL.')

st.write('Note: This app is for educational purposes only. Please respect copyright laws and YouTube\'s terms of service.')
