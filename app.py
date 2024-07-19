import streamlit as st
from pytube import YouTube
from pydub import AudioSegment
import os

# Funktion zum Herunterladen und Konvertieren von YouTube-Videos in MP3
def download_youtube_video(url):
    try:
        # Herunterladen des Videos
        yt = YouTube(url)
        video = yt.streams.filter(only_audio=True).first()
        out_file = video.download(output_path='.')

        # Konvertieren in MP3
        base, ext = os.path.splitext(out_file)
        new_file = base + '.mp3'
        audio = AudioSegment.from_file(out_file)
        audio.export(new_file, format='mp3')
        os.remove(out_file)  # Entfernen der ursprünglichen Datei

        return new_file, yt.title
    except Exception as e:
        st.error(f"Fehler beim Herunterladen und Konvertieren des Videos: {e}")
        return None, None

# Streamlit App
st.title("YouTube to MP3 Converter")

# Eingabefeld für die YouTube-URL
url = st.text_input("Geben Sie die URL des YouTube-Videos ein:")

if url:
    # Button zum Starten des Downloads und der Konvertierung
    if st.button("Download und Konvertierung starten"):
        with st.spinner('Herunterladen und Konvertieren...'):
            mp3_file, video_title = download_youtube_video(url)
            if mp3_file:
                st.success(f"Das Video '{video_title}' wurde erfolgreich in MP3 umgewandelt.")
                # Download-Link für die MP3-Datei
                st.markdown(f"[MP3-Datei herunterladen](./{mp3_file})")

# Hauptprogramm
if __name__ == "__main__":
    st.set_option('deprecation.showfileUploaderEncoding', False)
