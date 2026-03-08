# YouTube Downloader GUI - Fixed + URL Normalization + Cross-Platform Context Menu + NO OPUS AUDIO FIX + Open Folder Button
# Requirements:
# pip install yt-dlp pillow
# ffmpeg installed and in PATH (for merging & audio extraction)

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import yt_dlp
import threading
import os
import subprocess
import sys
from PIL import Image, ImageTk
import urllib.request
from io import BytesIO

class YouTubeDownloader:
    def __init__(self, root):
        self.root = root
        self.root.title("YouTube Downloader")
        self.root.geometry("850x750")
        self.download_dir = os.getcwd()
        self.fetch_timer = None
        self.cancel_flag = False
        self.current_thread = None

        # Notebook (tabs)
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)

        self.single_tab = ttk.Frame(self.notebook)
        self.channel_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.single_tab, text='Single Video')
        self.notebook.add(self.channel_tab, text='Channel Bulk')

        self.setup_single_tab()
        self.setup_channel_tab()

        # Global download folder
        dir_frame = ttk.Frame(root)
        dir_frame.pack(fill='x', padx=10, pady=5)
        ttk.Label(dir_frame, text="Download Folder:").pack(side='left')
        self.dir_entry = ttk.Entry(dir_frame, width=60)
        self.dir_entry.insert(0, self.download_dir)
        self.dir_entry.pack(side='left', padx=5, fill='x', expand=True)
        ttk.Button(dir_frame, text="Browse", command=self.browse_dir).pack(side='left')
        ttk.Button(dir_frame, text="Open Folder", command=self.open_download_folder).pack(side='left')  # ← NEW

        # === CROSS-PLATFORM RIGHT-CLICK CONTEXT MENUS ===
        self.add_context_menu(self.single_url_entry)
        self.add_context_menu(self.channel_url_entry)
        self.add_context_menu(self.dir_entry)

    def browse_dir(self):
        path = filedialog.askdirectory()
        if path:
            self.download_dir = path
            self.dir_entry.delete(0, tk.END)
            self.dir_entry.insert(0, path)

    # ===================== NEW: Open Download Folder (Windows + macOS + Linux) =====================
    def open_download_folder(self):
        try:
            if os.name == 'nt':                     # Windows
                os.startfile(self.download_dir)
            elif sys.platform == 'darwin':          # macOS
                subprocess.Popen(['open', self.download_dir])
            else:                                   # Linux
                subprocess.Popen(['xdg-open', self.download_dir])
        except Exception as e:
            messagebox.showerror("Error", f"Could not open folder:\n{e}")

    # ===================== SINGLE VIDEO TAB =====================
    def setup_single_tab(self):
        ttk.Label(self.single_tab, text="Video URL:").pack(anchor='w', pady=(10, 0))
        self.single_url_var = tk.StringVar()
        self.single_url_entry = ttk.Entry(self.single_tab, textvariable=self.single_url_var, width=80)
        self.single_url_entry.pack(fill='x', padx=10)
        self.single_url_var.trace('w', self.on_single_url_change)

        self.single_thumb_label = ttk.Label(self.single_tab)
        self.single_thumb_label.pack(pady=8)

        self.single_title_label = ttk.Label(self.single_tab, text="", font=("Helvetica", 12, "bold"), wraplength=600)
        self.single_title_label.pack()

        ttk.Label(self.single_tab, text="Select Quality:").pack(anchor='w', pady=(15, 5))
        self.quality_var = tk.StringVar(value="best")
        self.quality_options = []
        self.quality_frame = ttk.Frame(self.single_tab)
        self.quality_frame.pack(fill='x', padx=20)

        self.audio_only_var = tk.BooleanVar()
        ttk.Checkbutton(self.single_tab, text="Audio Only (best MP3)", variable=self.audio_only_var,
                        command=self.fetch_single_formats).pack(pady=10)

        # Progress
        self.single_prog_frame = ttk.Frame(self.single_tab)
        self.single_prog_frame.pack(fill='x', padx=20, pady=10)
        self.single_progressbar = ttk.Progressbar(self.single_prog_frame, orient='horizontal', length=400, mode='determinate')
        self.single_progressbar.pack(fill='x')
        self.single_prog_label = ttk.Label(self.single_prog_frame, text="Ready", anchor='center')
        self.single_prog_label.pack(fill='x', pady=3)

        btn_frame = ttk.Frame(self.single_tab)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="Download", command=self.download_single).pack(side='left', padx=10)
        self.single_cancel_btn = ttk.Button(btn_frame, text="Cancel", command=self.cancel_download, state='disabled')
        self.single_cancel_btn.pack(side='left', padx=10)

        self.fallback_label = ttk.Label(self.single_tab, text="", foreground="gray")
        self.fallback_label.pack(pady=5)

    def on_single_url_change(self, *args):
        if self.fetch_timer:
            self.root.after_cancel(self.fetch_timer)
        self.fetch_timer = self.root.after(800, self.fetch_single_formats)

    def fetch_single_formats(self):
        url = self.single_url_var.get().strip()
        if not url or not url.startswith("http"):
            return
        self.single_title_label.config(text="Fetching...")
        self.single_thumb_label.config(image='')
        for widget in self.quality_frame.winfo_children():
            widget.destroy()
        self.quality_options.clear()
        self.quality_var.set("best")
        self.fallback_label.config(text="")
        self.single_progressbar['value'] = 0
        self.single_prog_label.config(text="Fetching formats...")

        def fetch():
            try:
                with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                    info = ydl.extract_info(url, download=False)
                    thumb_url = info.get('thumbnail') or (info.get('thumbnails') or [{}])[0].get('url')
                    self.root.after(0, lambda: self.load_thumbnail(thumb_url, self.single_thumb_label))
                    self.root.after(0, lambda: self.single_title_label.config(text=info.get('title', 'Unknown Title')))

                    formats = info.get('formats', [])
                    audio_only = self.audio_only_var.get()
                    if audio_only:
                        best_audio = next((f for f in formats if f.get('vcodec') == 'none' and f.get('acodec') != 'none'), None)
                        if best_audio:
                            size = f"{best_audio.get('filesize_approx', 0)/1024/1024:.1f} MB" if best_audio.get('filesize_approx') else "~5-20 MB"
                            self.root.after(0, lambda: self.add_quality_option("audio", "bestaudio/best", f"Best Audio Only (MP3) ≈ {size}", ""))
                        self.root.after(0, lambda: self.single_prog_label.config(text="Ready – audio only"))
                        return

                    video_formats = [f for f in formats if f.get('vcodec') != 'none' and f.get('height')]
                    video_formats.sort(key=lambda f: (f.get('height', 0), f.get('fps', 0), f.get('filesize_approx', 0)), reverse=True)

                    tiers = [
                        (9999, "Best Quality (highest available)"),
                        (1080, "1080p HD"),
                        (720, "720p HD"),
                        (480, "480p"),
                        (360, "360p or lower")
                    ]
                    added_heights = set()
                    for max_h, title in tiers:
                        for f in video_formats:
                            h = f.get('height', 0)
                            if h in added_heights or (h > max_h and max_h != 9999):
                                continue
                            size = f"{f.get('filesize_approx', 0)/1024/1024:.1f} MB" if f.get('filesize_approx') else "?"
                            codec = "AVC" if 'avc' in f.get('vcodec', '') else "VP9" if 'vp' in f.get('vcodec', '') else ""
                            note = f"≈ {size}" + (f" ({codec})" if codec else "")
                            # === OPUS FIX: Always prefer AVC video + AAC audio (m4a) for perfect compatibility ===
                            if max_h == 9999:
                                fmt_str = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best"
                            else:
                                fmt_str = f"bestvideo[height<={max_h}][ext=mp4]+bestaudio[ext=m4a]/best[height<={max_h}]/best"
                            display = f"{title} ({h}p)" if h else title
                            self.root.after(0, lambda v=title.lower().replace(" ", "_"), fs=fmt_str, d=display, n=note: self.add_quality_option(v, fs, d, n))
                            added_heights.add(h)
                            break
                    if not added_heights:
                        self.root.after(0, lambda: self.add_quality_option("any", "best", "Any available video", ""))
                    self.root.after(0, lambda: self.single_prog_label.config(text="Quality options loaded ✓"))
            except Exception as e:
                self.root.after(0, lambda: [messagebox.showerror("Error", str(e)), self.single_prog_label.config(text="Failed to fetch formats")])

        threading.Thread(target=fetch, daemon=True).start()

    def add_quality_option(self, value, fmt_str, display_label, note):
        rb = ttk.Radiobutton(self.quality_frame, text=f"{display_label} {note}", variable=self.quality_var, value=value)
        rb.pack(anchor='w', pady=3)
        self.quality_options.append((value, fmt_str, display_label, note))

    def download_single(self):
        url = self.single_url_var.get().strip()
        if not url:
            messagebox.showerror("Error", "Enter a URL")
            return
        selected_val = self.quality_var.get()
        selected_fmt = next((fs for val, fs, _, _ in self.quality_options if val == selected_val), "best")
        if self.audio_only_var.get():
            selected_fmt = "bestaudio/best"

        self.cancel_flag = False
        self.single_cancel_btn.config(state='normal')
        self.single_progressbar['value'] = 0
        self.single_prog_label.config(text="Starting...")

        def dl():
            try:
                def progress_hook(d):
                    if self.cancel_flag:
                        raise yt_dlp.utils.DownloadCancelled("Cancelled by user")
                    if d['status'] == 'downloading':
                        percent_str = d.get('_percent_str', '0%').strip('%')
                        try:
                            percent = float(percent_str) if percent_str else 0.0
                        except (ValueError, TypeError):
                            percent = 0.0
                        eta = d.get('_eta_str', '--')
                        speed = d.get('_speed_str', '--')
                        downloaded = d.get('downloaded_bytes', 0)
                        total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                        size_str = f"{downloaded/1024/1024:.1f} / {total/1024/1024:.1f} MB" if total > 0 else f"{downloaded/1024/1024:.1f} MB"
                        text = f"{percent:.1f}% | {speed} | ETA: {eta} | {size_str}"
                        self.root.after(0, lambda p=percent, t=text: self.update_single_progress(p, t))
                    elif d['status'] == 'finished':
                        self.root.after(0, lambda: self.update_single_progress(100, "Processing..."))

                opts = {
                    'format': selected_fmt,
                    'outtmpl': os.path.join(self.download_dir, '%(title)s.%(ext)s'),
                    'progress_hooks': [progress_hook],
                    'merge_output_format': 'mp4',
                    'continuedl': True,
                }
                if self.audio_only_var.get():
                    opts['postprocessors'] = [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}]

                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.download([url])
                self.root.after(0, lambda: messagebox.showinfo("Success", "Download finished!"))
            except yt_dlp.utils.DownloadCancelled:
                self.root.after(0, lambda: messagebox.showinfo("Cancelled", "Download cancelled"))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
            finally:
                self.root.after(0, self.finish_single_ui)

        self.current_thread = threading.Thread(target=dl, daemon=True)
        self.current_thread.start()

    def update_single_progress(self, percent, text):
        self.single_progressbar['value'] = percent
        self.single_prog_label.config(text=text)

    def finish_single_ui(self):
        self.single_cancel_btn.config(state='disabled')
        self.single_progressbar['value'] = 0
        self.single_prog_label.config(text="Ready")

    # ===================== CHANNEL BULK TAB =====================
    def setup_channel_tab(self):
        ttk.Label(self.channel_tab, text="Channel URL:").pack(anchor='w', pady=(10, 0))
        self.channel_url_var = tk.StringVar()
        self.channel_url_entry = ttk.Entry(self.channel_tab, textvariable=self.channel_url_var, width=80)
        self.channel_url_entry.pack(fill='x', padx=10)
        self.channel_url_var.trace('w', self.on_channel_url_change)

        self.channel_thumb_label = ttk.Label(self.channel_tab)
        self.channel_thumb_label.pack(pady=8)

        self.channel_name_label = ttk.Label(self.channel_tab, text="", font=("Helvetica", 12, "bold"))
        self.channel_name_label.pack()

        ttk.Label(self.channel_tab, text="Download:").pack(anchor='w', pady=(10, 0))
        self.channel_type_var = tk.StringVar(value='videos')
        ttk.Radiobutton(self.channel_tab, text="Videos only", variable=self.channel_type_var, value='videos').pack(anchor='w')
        ttk.Radiobutton(self.channel_tab, text="Shorts only", variable=self.channel_type_var, value='shorts').pack(anchor='w')
        ttk.Radiobutton(self.channel_tab, text="Both (Videos + Shorts)", variable=self.channel_type_var, value='both').pack(anchor='w')

        ttk.Label(self.channel_tab, text="Quality:").pack(anchor='w', pady=(10, 0))
        self.quality_var = tk.StringVar(value='best')
        for q in ['best', '720p', '480p', 'worst']:
            ttk.Radiobutton(self.channel_tab, text=q.upper(), variable=self.quality_var, value=q).pack(anchor='w')

        self.channel_audio_only_var = tk.BooleanVar()
        ttk.Checkbutton(self.channel_tab, text="Audio Only (MP3)", variable=self.channel_audio_only_var).pack(pady=8)

        # Progress
        self.channel_prog_frame = ttk.Frame(self.channel_tab)
        self.channel_prog_frame.pack(fill='x', padx=20, pady=10)
        self.channel_progressbar = ttk.Progressbar(self.channel_prog_frame, orient='horizontal', length=400, mode='determinate')
        self.channel_progressbar.pack(fill='x')
        self.channel_prog_label = ttk.Label(self.channel_prog_frame, text="Ready", anchor='center')
        self.channel_prog_label.pack(fill='x', pady=3)

        btn_frame = ttk.Frame(self.channel_tab)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="Start Bulk Download", command=self.download_channel).pack(side='left', padx=10)
        self.channel_cancel_btn = ttk.Button(btn_frame, text="Cancel", command=self.cancel_download, state='disabled')
        self.channel_cancel_btn.pack(side='left', padx=10)

    def on_channel_url_change(self, *args):
        if self.fetch_timer:
            self.root.after_cancel(self.fetch_timer)
        self.fetch_timer = self.root.after(800, self.load_channel_preview)

    def load_channel_preview(self):
        url = self.channel_url_var.get().strip()
        if not url or not url.startswith("http"):
            return
        self.channel_name_label.config(text="Loading preview...")
        self.channel_thumb_label.config(image='')

        def fetch():
            try:
                with yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': True}) as ydl:
                    info = ydl.extract_info(url, download=False)
                    thumb_url = info.get('thumbnail') or (info.get('thumbnails') or [{}])[0].get('url')
                    self.root.after(0, lambda: self.load_thumbnail(thumb_url, self.channel_thumb_label))
                    self.root.after(0, lambda: self.channel_name_label.config(text=info.get('uploader', 'Channel')))
            except:
                self.root.after(0, lambda: self.channel_name_label.config(text="Preview unavailable"))

        threading.Thread(target=fetch, daemon=True).start()

    # ===================== SHARED HELPERS =====================
    def load_thumbnail(self, url, label):
        if not url:
            return
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                data = response.read()
            img = Image.open(BytesIO(data))
            img = img.resize((220, 165), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            label.config(image=photo)
            label.image = photo
        except:
            pass

    # ===================== CROSS-PLATFORM RIGHT-CLICK CONTEXT MENU =====================
    def add_context_menu(self, entry_widget):
        """Add right-click context menu (Cut / Copy / Paste / Select All / Clear)
        Works on Windows (right-click) + macOS (right-click + Control-click)"""
        menu = tk.Menu(self.root, tearoff=0)
        
        menu.add_command(label="Cut", command=lambda: entry_widget.event_generate("<<Cut>>"))
        menu.add_command(label="Copy", command=lambda: entry_widget.event_generate("<<Copy>>"))
        menu.add_command(label="Paste", command=lambda: entry_widget.event_generate("<<Paste>>"))
        menu.add_separator()
        menu.add_command(label="Select All", command=lambda: entry_widget.select_range(0, tk.END))
        menu.add_command(label="Clear", command=lambda: entry_widget.delete(0, tk.END))
        
        def show_menu(event):
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()
        
        entry_widget.bind("<Button-3>", show_menu)           # Right-click (Windows + macOS)
        entry_widget.bind("<Control-Button-1>", show_menu)   # Control + Click (macOS trackpad)
        entry_widget.bind("<Button-2>", show_menu)           # Extra safety for macOS

    # ===================== URL NORMALIZATION + FIXED PROGRESS HOOK + NO-OPUS FIX =====================
    def download_channel(self):
        raw_input = self.channel_url_var.get().strip()
        if not raw_input:
            messagebox.showerror("Error", "Enter a channel URL")
            return

        # === URL AUTO-FIX ===
        url = raw_input.rstrip('/')
        common_tabs = ['/shorts', '/videos', '/live', '/streams', '/playlists', '/community', '/about']
        for tab in common_tabs:
            if url.endswith(tab):
                url = url[:-len(tab)].rstrip('/')
        if '/@' in url:
            parts = url.split('/@')
            if len(parts) > 1:
                handle = parts[1].split('/')[0]
                url = f"https://www.youtube.com/@{handle}"
        url = url.strip().rstrip('/')

        if 'watch?v=' in url or 'youtu.be/' in url:
            messagebox.showwarning(
                "Video URL detected",
                "This looks like a single video link.\n\n"
                "For channel bulk download please use:\n"
                "• @username\n"
                "• https://www.youtube.com/@username"
            )

        # === Normal download logic ===
        mode = self.channel_type_var.get()
        quality = self.quality_var.get()
        # === OPUS FIX: Always force AAC audio (m4a) + MP4-compatible video ===
        quality_map = {
            'best': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best',
            '720p': 'bv[height<=720][ext=mp4]+ba[ext=m4a]/best',
            '480p': 'bv[height<=480][ext=mp4]+ba[ext=m4a]/best',
            'worst': 'worstvideo[ext=mp4]+worstaudio[ext=m4a]/best'
        }
        fmt = quality_map.get(quality, 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best')
        if self.channel_audio_only_var.get():
            fmt = 'bestaudio/best'

        base_out = os.path.join(self.download_dir, '%(uploader)s')
        urls_and_templates = []
        if mode in ('videos', 'both'):
            urls_and_templates.append((url, os.path.join(base_out, '%(title)s.%(ext)s')))
        if mode in ('shorts', 'both'):
            urls_and_templates.append((url + '/shorts', os.path.join(base_out, 'Shorts', '%(title)s.%(ext)s')))

        self.cancel_flag = False
        self.channel_cancel_btn.config(state='normal')
        self.channel_progressbar['value'] = 0
        self.channel_prog_label.config(text="Starting bulk download...")

        def dl_bulk():
            try:
                def progress_hook(d):
                    if self.cancel_flag:
                        raise yt_dlp.utils.DownloadCancelled("Cancelled")
                    if d['status'] == 'downloading':
                        percent_str = d.get('_percent_str', '0%').strip('%')
                        try:
                            percent = float(percent_str) if percent_str else 0.0
                        except (ValueError, TypeError):
                            percent = 0.0
                        eta = d.get('_eta_str', '--')
                        speed = d.get('_speed_str', '--')
                        downloaded = d.get('downloaded_bytes', 0)
                        total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                        size_str = f"{downloaded/1024/1024:.1f} / {total/1024/1024:.1f} MB" if total > 0 else f"{downloaded/1024/1024:.1f} MB"
                        text = f"Current: {percent:.1f}% | {speed} | ETA: {eta} | {size_str}"
                        self.root.after(0, lambda p=percent, t=text: self.update_channel_progress(p, t))
                    elif d['status'] == 'finished':
                        self.root.after(0, lambda: self.update_channel_progress(0, "Processing next video..."))

                opts_base = {
                    'format': fmt,
                    'progress_hooks': [progress_hook],
                    'ignoreerrors': True,
                    'continuedl': True,
                    'noplaylist': False,
                    'merge_output_format': 'mp4',   # Forces .mp4 with AAC audio
                }
                if self.channel_audio_only_var.get():
                    opts_base['postprocessors'] = [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}]

                for playlist_url, outtmpl in urls_and_templates:
                    if self.cancel_flag:
                        break
                    opts = opts_base.copy()
                    opts['outtmpl'] = outtmpl
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        ydl.download([playlist_url])

                self.root.after(0, lambda: messagebox.showinfo("Success", "Channel download finished!"))
            except yt_dlp.utils.DownloadCancelled:
                self.root.after(0, lambda: messagebox.showinfo("Cancelled", "Download cancelled"))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
            finally:
                self.root.after(0, self.finish_channel_ui)

        self.current_thread = threading.Thread(target=dl_bulk, daemon=True)
        self.current_thread.start()

    def update_channel_progress(self, percent, text):
        self.channel_progressbar['value'] = percent
        self.channel_prog_label.config(text=text)

    def finish_channel_ui(self):
        self.channel_cancel_btn.config(state='disabled')
        self.channel_progressbar['value'] = 0
        self.channel_prog_label.config(text="Ready")

    def cancel_download(self):
        self.cancel_flag = True
        self.root.after(0, lambda: messagebox.showinfo("Cancelling", "Cancelling current download..."))


if __name__ == "__main__":
    root = tk.Tk()
    app = YouTubeDownloader(root)
    root.mainloop()
