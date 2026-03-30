import customtkinter as ctk
import yt_dlp
import threading
import os
import sys
import time
from tkinter import filedialog, BooleanVar
from urllib.parse import urlparse, parse_qs, urlunparse
import arabic_reshaper
from bidi.algorithm import get_display
def fix_arabic(text):
    return arabic_reshaper.reshape(text)
def get_ffmpeg_path():
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    
    ffmpeg_exe = "ffmpeg.exe" if os.name == 'nt' else "ffmpeg"
    full_path = os.path.join(base_path, ffmpeg_exe)
    
    if os.path.exists(full_path):
        return full_path
    return None

def format_time(seconds):
    if not seconds:
        return "N/A"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

def format_size(bytes_size):
    if not bytes_size:
        return "N/A"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024.0

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Downloader-KAS")
        self.geometry("900x850")
        
        self.download_path = os.path.join(os.path.expanduser("~"), "Downloads")
        self.video_items = []
        self.current_downloading_item = None
        self.is_paused = False
        self.cancel_fetch_flag = False 

        self.label = ctk.CTkLabel(self, text="Downloader-KAS", font=("Arial", 24, "bold"))
        self.label.pack(pady=10)

        self.input_label = ctk.CTkLabel(self, text="Paste Playlist or Video URL:", font=("Arial", 12))
        self.input_label.pack()
        
        self.textbox = ctk.CTkTextbox(self, width=650, height=100)
        self.textbox.pack(pady=5)
        
        self.textbox.bind("<Control-a>", self.select_all_text)
        self.textbox.bind("<Control-A>", self.select_all_text)
        self.textbox.bind("<KeyPress>", self.on_keypress)
        self.textbox.bind("<Control-v>", self.on_paste)
        self.textbox.bind("<Control-V>", self.on_paste)

        self.single_video_var = ctk.BooleanVar(value=False)
        self.single_video_checkbox = ctk.CTkCheckBox(self, text="Single Video Only (Ignore Playlist)", variable=self.single_video_var)
        self.single_video_checkbox.pack(pady=5)

        self.fetch_controls_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.fetch_controls_frame.pack(pady=5)

        self.fetch_button = ctk.CTkButton(self.fetch_controls_frame, text="Fetch Info", command=self.start_fetch_thread, fg_color="#28a745", hover_color="#218838")
        self.fetch_button.pack(side="left", padx=5)

        self.stop_fetch_button = ctk.CTkButton(self.fetch_controls_frame, text="Stop Fetch", command=self.stop_fetch, fg_color="#dc3545", hover_color="#c82333", state="disabled")
        self.stop_fetch_button.pack(side="left", padx=5)
        self.restart_btn = ctk.CTkButton(
            self.fetch_controls_frame, 
            text="Restart App 🔄", 
            command=self.restart_program, 
            fg_color="#6c757d", 
            hover_color="#5a6268"
        )
        self.restart_btn.pack(side="left", padx=5)
        self.buttons_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.buttons_frame.pack(fill="x", padx=20, pady=5)
        
        self.select_all_btn = ctk.CTkButton(self.buttons_frame, text="Select All", width=100, fg_color="#17a2b8", command=self.select_all)
        self.select_all_btn.pack(side="left", padx=5)
        
        self.deselect_all_btn = ctk.CTkButton(self.buttons_frame, text="Deselect All", width=100, fg_color="#6c757d", command=self.deselect_all)
        self.deselect_all_btn.pack(side="left", padx=5)

        self.header_frame = ctk.CTkFrame(self, height=30, fg_color="#343a40")
        self.header_frame.pack(fill="x", padx=20, pady=(10, 0))
        
        ctk.CTkLabel(self.header_frame, text="✔", width=30, text_color="white", font=("Arial", 12, "bold")).grid(row=0, column=0, padx=5, pady=5)
        ctk.CTkLabel(self.header_frame, text="Video Title", width=350, anchor="w", text_color="white", font=("Arial", 12, "bold")).grid(row=0, column=1, padx=5, pady=5)
        ctk.CTkLabel(self.header_frame, text="Duration", width=80, text_color="white", font=("Arial", 12, "bold")).grid(row=0, column=2, padx=5, pady=5)
        ctk.CTkLabel(self.header_frame, text="Size", width=80, text_color="white", font=("Arial", 12, "bold")).grid(row=0, column=3, padx=5, pady=5)
        ctk.CTkLabel(self.header_frame, text="Status", width=100, text_color="white", font=("Arial", 12, "bold")).grid(row=0, column=4, padx=5, pady=5)
        ctk.CTkLabel(self.header_frame, text="Progress", width=80, text_color="white", font=("Arial", 12, "bold")).grid(row=0, column=5, padx=5, pady=5)

        self.playlist_frame = ctk.CTkScrollableFrame(self, width=850, height=250)
        self.playlist_frame.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        self.bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.bottom_frame.pack(fill="x", padx=20, pady=10)

        self.quality_var = ctk.StringVar(value="Highest Video Quality")
        self.optionmenu = ctk.CTkOptionMenu(self.bottom_frame, 
        values=["Highest Video Quality", "1080p", "720p", "480p", "Audio Only (MP3)"],
            variable=self.quality_var)
        self.optionmenu.pack(side="left", padx=10)

        self.path_button = ctk.CTkButton(self.bottom_frame, text="Change Save Location", fg_color="transparent", border_width=1, command=self.select_path)
        self.path_button.pack(side="left", padx=10)

        self.path_label = ctk.CTkLabel(self.bottom_frame, text=f"Path: {self.download_path}", text_color="gray", font=("Arial", 11))
        self.path_label.pack(side="left", padx=10)

        self.controls_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.controls_frame.pack(pady=10)

        self.download_button = ctk.CTkButton(self.controls_frame, text="Start Download", command=self.start_download_thread, fg_color="#1f538d", height=40, state="disabled")
        self.download_button.pack(side="left", padx=5)

        self.pause_button = ctk.CTkButton(self.controls_frame, text="Pause ⏸", command=self.toggle_pause, fg_color="#ffc107", text_color="black", hover_color="#e0a800", height=40, state="disabled", width=100)
        self.pause_button.pack(side="left", padx=5)

        self.status_label = ctk.CTkLabel(self, text="Ready", text_color="gray", font=("Arial", 12))
        self.status_label.pack(pady=5)
        import webbrowser

        def open_link(event):
            webbrowser.open_new("https://www.facebook.com/Kareem0Salman?locale=ar_AR")

        self.footer_label = ctk.CTkLabel(
            self, 
            text="Developed by: Kareem Salman\n01097783253", 
            font=("Arial", 11, "underline"), 
            text_color="#1f538d", 
            cursor="hand2"
        )
        self.footer_label.pack(side="bottom", pady=10)
        self.footer_label.bind("<Button-1>", open_link)

    def select_all_text(self, event=None):
        self.textbox.tag_add("sel", "1.0", "end")
        return "break"

    def clear_selection(self):
        if self.textbox.tag_ranges("sel"):
            self.textbox.delete("sel.first", "sel.last")

    def on_paste(self, event=None):
        self.clear_selection()
        return None

    def on_keypress(self, event):
        if event.char or event.keysym in ("Return", "BackSpace", "Delete"):
            self.clear_selection()
        return None

    def select_all(self):
        for item in self.video_items:
            item["var"].set(True)

    def deselect_all(self):
        for item in self.video_items:
            item["var"].set(False)

    def select_path(self):
        path = filedialog.askdirectory()
        if path:
            self.download_path = path
            self.path_label.configure(text=f"Path: {path}")

    def update_status(self, text, color):
        self.status_label.configure(text=text, text_color=color)

    def update_item_status(self, item, status_text, color, prog_text=None, size_text=None):
        item['status_lbl'].configure(text=status_text, text_color=color)
        if prog_text:
            item['prog_lbl'].configure(text=prog_text)
        if size_text:
            item['size_lbl'].configure(text=size_text)

    def toggle_pause(self):
        self.is_paused = not self.is_paused
        
        if self.is_paused:
            self.pause_button.configure(text="Resume ▶", fg_color="#28a745", text_color="white")
            self.update_status("Paused ⏸", "red")
            if self.current_downloading_item:
                self.update_item_status(self.current_downloading_item, "Paused", "red")
        else:
            self.pause_button.configure(text="Pause ⏸", fg_color="#ffc107", text_color="black")
            self.update_status("Resuming...", "orange")
            if self.current_downloading_item:
                self.update_item_status(self.current_downloading_item, "Downloading...", "orange")

    def stop_fetch(self):
        self.cancel_fetch_flag = True
        self.stop_fetch_button.configure(state="disabled")
        self.update_status("Cancelling fetch...", "orange")

    def start_fetch_thread(self):
        raw_input = self.textbox.get("1.0", "end-1c").strip()
        if not raw_input:
            self.update_status("Error: Please enter at least one URL!", "red")
            return
            
        urls = [line.strip() for line in raw_input.split('\n') if line.strip()]
        
        self.cancel_fetch_flag = False
        self.fetch_button.configure(state="disabled")
        self.stop_fetch_button.configure(state="normal")
        
        for widget in self.playlist_frame.winfo_children():
            widget.destroy()
        self.video_items.clear()

        thread = threading.Thread(target=self.fetch_logic, args=(urls,))
        thread.daemon = True
        thread.start()
    def fetch_logic(self, urls):
        video_count = 0
        
        for url in urls:
            if self.cancel_fetch_flag: 
                break
                
            current_url = url.strip()
            
            if "watch?v=" in current_url and "&list=" in current_url and not self.single_video_var.get():
                current_url = current_url.split("&list=")[0]
                self.after(0, self.update_status, "Smart Detection: Video Only Mode", "#17a2b8")
            
            elif self.single_video_var.get():
                if "&list=" in current_url:
                    current_url = current_url.split("&list=")[0]
                if "?list=" in current_url:
                    current_url = current_url.split("?list=")[0]

            
            ydl_opts_check = {
                'quiet': True, 
                'extract_flat': 'in_playlist',
                'no_warnings': True,
                'ignoreerrors': True,
                'format': 'best', 
                'noplaylist': True if "watch?v=" in current_url else False 
            }

            self.after(0, self.update_status, f"Fetching: {current_url[:35]}...", "orange")
            
            try:
                with yt_dlp.YoutubeDL(ydl_opts_check) as ydl:
                    info = ydl.extract_info(current_url, download=False)
                    
                    if not info:
                        continue

                    if 'entries' in info and not ydl_opts_check['noplaylist']:
                        entries = [e for e in info['entries'] if e is not None]
                        self.after(0, self.update_status, f"Found Playlist ({len(entries)} items).", "green")
                        for entry in entries:
                            if self.cancel_fetch_flag: break
                            self.after(0, self.add_row_to_table, entry, video_count)
                            video_count += 1
                    else:
                        self.after(0, self.add_row_to_table, info, video_count)
                        video_count += 1
                        
            except Exception as e:
                print(f"Error fetching {current_url}: {e}")

        self.after(0, lambda: self.update_status(f"Fetch Completed! ({video_count} videos found)", "green"))
        self.after(0, lambda: self.download_button.configure(state="normal" if self.video_items else "disabled"))
        self.after(0, lambda: [self.fetch_button.configure(state="normal"), self.stop_fetch_button.configure(state="disabled")])
    def add_row_to_table(self, entry, idx):
        raw_title = entry.get('title', 'Unknown Title')
        display_title = fix_arabic(raw_title)
        video_url = entry.get('original_url') or entry.get('webpage_url') or entry.get('url')
        duration = format_time(entry.get('duration'))
        pre_size = entry.get('filesize_approx') or entry.get('filesize')
        size_str = format_size(pre_size)
        
        row_frame = ctk.CTkFrame(self.playlist_frame, fg_color="transparent")
        row_frame.pack(fill="x", pady=2)

        var = BooleanVar(value=True)
        
        cb = ctk.CTkCheckBox(row_frame, text="", variable=var, width=30)
        cb.grid(row=0, column=0, padx=5)

        title_lbl = ctk.CTkLabel(row_frame, text=display_title[:70], width=350, anchor="w", font=("Arial", 12))
        title_lbl.grid(row=0, column=1, padx=5)

        dur_lbl = ctk.CTkLabel(row_frame, text=duration, width=80, font=("Arial", 12))
        dur_lbl.grid(row=0, column=2, padx=5)

        size_lbl = ctk.CTkLabel(row_frame, text=size_str, width=80, font=("Arial", 12))
        size_lbl.grid(row=0, column=3, padx=5)

        status_lbl = ctk.CTkLabel(row_frame, text="Pending", width=100, text_color="gray", font=("Arial", 12))
        status_lbl.grid(row=0, column=4, padx=5)

        prog_lbl = ctk.CTkLabel(row_frame, text="0%", width=80, font=("Arial", 12))
        prog_lbl.grid(row=0, column=5, padx=5)

        self.video_items.append({
            "url": video_url,
            "var": var, 
            "title": raw_title, 
            "size_lbl": size_lbl,
            "status_lbl": status_lbl,
            "prog_lbl": prog_lbl
        })
    def restart_program(self):
        """إعادة تشغيل البرنامج بالكامل"""
        python = sys.executable
        os.execl(python, python, *sys.argv)
    def progress_hook(self, d):
        if not self.current_downloading_item:
            return

        item = self.current_downloading_item

        while self.is_paused:
            time.sleep(0.5)

        if d['status'] == 'downloading':
            downloaded = d.get('downloaded_bytes', 0)
            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            
            prog_text = None
            size_text = None
            
            if total > 0:
                percent = (downloaded / total) * 100
                prog_text = f"{percent:.1f}%"
                size_text = format_size(total)

            self.after(0, self.update_item_status, item, "Downloading...", "orange", prog_text, size_text)

        elif d['status'] == 'finished':
            self.after(0, self.update_item_status, item, "Processing...", "#17a2b8", "100%")

    def start_download_thread(self):
        selected_items = [item for item in self.video_items if item['var'].get()]
        
        if not selected_items:
            self.update_status("Error: No videos selected!", "red")
            return

        self.download_button.configure(state="disabled")
        self.fetch_button.configure(state="disabled")
        self.pause_button.configure(state="normal")
        self.is_paused = False
        
        self.update_status("Starting Download...", "orange")
        
        thread = threading.Thread(target=self.download_logic, args=(selected_items,))
        thread.daemon = True
        thread.start()

    def download_logic(self, selected_items):
        quality_choice = self.quality_var.get()
        
        if "Audio" in quality_choice:
            format_str = "bestaudio/best"
        elif "1080p" in quality_choice:
            format_str = "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best"
        elif "720p" in quality_choice:
            format_str = "bestvideo[height<=720]+bestaudio/best[height<=720]/best"
        elif "480p" in quality_choice:
            format_str = "bestvideo[height<=480]+bestaudio/best[height<=480]/best"
        else:
            format_str = "bestvideo+bestaudio/best"

        ydl_opts = {
            'format': format_str,
            'outtmpl': os.path.join(self.download_path, '%(title)s.%(ext)s'),
            'progress_hooks': [self.progress_hook],
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True, 
            'merge_output_format': 'mp4',
        }

        ffmpeg_loc = get_ffmpeg_path()
        if ffmpeg_loc:
            ydl_opts['ffmpeg_location'] = ffmpeg_loc

        if "Audio" in quality_choice:
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]

        for index, item in enumerate(selected_items):
            video_url = item.get('url')
            if not video_url:
                continue

            self.after(0, self.update_status, f"Downloading {index+1}/{len(selected_items)}...", "orange")
            self.current_downloading_item = item
            
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    error_code = ydl.download([video_url])
                    if error_code != 0:
                        raise Exception("Download returned error code")

                self.after(0, self.update_item_status, item, "Done ✅", "green")
            except Exception as e:
                self.after(0, self.update_item_status, item, "Error ❌", "red")
                print(f"Download Error on {video_url}: {e}")

        self.after(0, self.update_status, "All Selected Tasks Completed! ✅", "green")
        def reset_ui():
            self.download_button.configure(state="normal")
            self.fetch_button.configure(state="normal")
            self.pause_button.configure(state="disabled", text="Pause ⏸", fg_color="#ffc107", text_color="black")
            
        self.after(0, reset_ui)
        self.current_downloading_item = None
if __name__ == "__main__":
    app = App()
    app.mainloop()