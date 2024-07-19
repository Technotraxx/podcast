import streamlit as st
from pytube import YouTube
import io
import re

def is_valid_youtube_url(url):
    # Einfache Regex zur Überprüfung des YouTube-URL-Formats
    youtube_regex = r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/'
    return re.match(youtube_regex, url) is not None

def download_audio(url):
    try:
        yt = YouTube(url)
        audio_stream = yt.streams.filter(only_audio=True).first()
        if not audio_stream:
            raise Exception("Kein Audiostream gefunden.")
        buffer = io.BytesIO()
        audio_stream.stream_to_buffer(buffer)
        buffer.seek(0)
        return buffer, yt.title
    except Exception as e:
        raise Exception(f"Fehler beim Herunterladen: {str(e)}")

st.title('YouTube zu MP3 Konverter')

url = st.text_input('Geben Sie die YouTube-URL ein:')
if st.button('Zu MP3 konvertieren'):
    if url:
        if not is_valid_youtube_url(url):
            st.error('Bitte geben Sie eine gültige YouTube-URL ein.')
        else:
            try:
                with st.spinner('Konvertiere...'):
                    buffer, title = download_audio(url)
                    st.success('Konvertierung abgeschlossen!')
                    
                    st.download_button(
                        label="MP3 herunterladen",
                        data=buffer,
                        file_name=f"{title}.mp3",
                        mime="audio/mpeg"
                    )
            except Exception as e:
                st.error(f"Ein Fehler ist aufgetreten: {str(e)}")
                st.info("Bitte versuchen Sie es später erneut oder probieren Sie eine andere URL.")
    else:
        st.warning('Bitte geben Sie eine YouTube-URL ein.')

st.write('Hinweis: Diese App dient nur Bildungszwecken. Bitte beachten Sie die Urheberrechtsgesetze und YouTubes Nutzungsbedingungen.')
