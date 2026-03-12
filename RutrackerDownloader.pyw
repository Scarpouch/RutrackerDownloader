import tkinter as tk
from tkinter import messagebox, filedialog, ttk
import subprocess
import os
import threading
import re
import configparser
from datetime import datetime
import logging
import requests
from urllib.parse import urlparse
import time

class RutrackerDownloader:
    def __init__(self):
        self.process = None
        self.is_cancelled = False
        self.folder_path = None
        self.setup_logging()
        self.config = self.load_config()
        self.create_gui()
    
    def setup_logging(self):

        #Создание папки логов
        self.log_dir = "data/logs"
        os.makedirs(self.log_dir, exist_ok=True)
        
        #Имя файла по дате
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = os.path.join(self.log_dir, f"downloader_{today}.log")
        
        #Очистка существующих handlers
        self.logger = logging.getLogger('RutrackerDownloader')
        self.logger.setLevel(logging.DEBUG)
        for handler in self.logger.handlers[:]: self.logger.removeHandler(handler)
        for handler in logging.root.handlers[:]: logging.root.removeHandler(handler)
        
        #File handler - полное логирование в файл
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        
        #Console handler - только INFO+ в консоль
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        #Форматы вывода
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        
        #Привязка форматов и добавление handlers
        file_handler.setFormatter(file_formatter)
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        
        self.logger.info("Логгер инициализирован")
        self.log_file_path = log_file
        print(f"Лог файл: {log_file}")

    def log(self, message): self.logger.info(message)
    def log_debug(self, message): self.logger.debug(message)
    def log_error(self, message): self.logger.error(message)
    
    def load_config(self):
        config_file = 'data/downloader.ini'
        config = configparser.ConfigParser()
        os.makedirs(os.path.dirname(config_file), exist_ok=True)
        
        default_config = {
            'window': {'width': '600', 'height': '450', 'x': '100', 'y': '100'},
            'paths': {'last_folder': ''}
        }
        
        if os.path.exists(config_file):
            config.read(config_file, encoding='utf-8')
            self.log("Конфиг загружен")
        else:
            #Инициализация дефолтных значений
            for section, options in default_config.items():
                config.add_section(section)
                for key, value in options.items():
                    config.set(section, key, value)
            with open(config_file, 'w', encoding='utf-8') as f:
                config.write(f)
            self.log("Создан новый конфиг")
        return config
    
    def save_config(self):
        try:
            self.root.update()
            self.config.set('window', 'width', str(self.root.winfo_width()))
            self.config.set('window', 'height', str(self.root.winfo_height()))
            self.config.set('window', 'x', str(self.root.winfo_x()))
            self.config.set('window', 'y', str(self.root.winfo_y()))
            
            self.config.set('paths', 'last_folder', self.folder_path or '')
            
            with open('data/downloader.ini', 'w', encoding='utf-8') as f:
                self.config.write(f)
            self.log("Конфиг сохранен")
        except Exception as e:
            self.log_error(f"Ошибка сохранения конфига: {e}")
    
    def create_gui(self):
        self.log("Создание GUI")
        
        self.root = tk.Tk()
        self.root.title("Rutracker Downloader")
        
        #Восстановление геометрии окна
        width = int(self.config.get('window', 'width', fallback='600'))
        height = int(self.config.get('window', 'height', fallback='450'))
        x = int(self.config.get('window', 'x', fallback='100'))
        y = int(self.config.get('window', 'y', fallback='100'))
        
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.resizable(True, True)
        self.root.minsize(420, 350)
        
        #Основной контейнер
        frame = tk.Frame(self.root, padx=20, pady=20)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        #Заголовок
        tk.Label(frame, text="Скачать видео с ресурса", font=("Arial", 17, "bold")).pack(pady=0)
        tk.Label(frame, text="youtube.com / rutube.ru / twitch.tv и т.д.", font=("Arial", 15, "bold")).pack(pady=(0,10))
        tk.Label(frame, text="Ссылка:", fg="gray", font=("Arial", 15)).pack(anchor='w')
        
        #Поле ввода ссылки
        self.entry = tk.Entry(frame, font=("Arial", 15), bg="white")
        self.entry.pack(fill=tk.X, pady=(0,10))
        self.entry.insert(0, "https://")
        
        #Выбор папки
        self.folder_label = tk.Label(frame, 
                                   text="📁 Выберите папку для сохранения видео", 
                                   fg="gray", font=("Arial", 12), 
                                   wraplength=500, justify="left")
        self.folder_label.pack(anchor='w', pady=(0,5))
        
        tk.Button(frame, text="📂 Выбрать папку", command=self.choose_folder, 
                 bg="#2196F3", fg="white", font=("Arial", 15, "bold"), 
                 relief="flat", padx=20).pack(pady=5)
        
        #Кнопки управления
        btn_frame = tk.Frame(frame)
        btn_frame.pack(pady=10)
        
        self.download_btn = tk.Button(btn_frame, text="Скачать", command=self.download_video,
                                    bg="#4CAF50", fg="white", width=14, font=("Arial", 15, "bold"),
                                    relief="flat")
        self.download_btn.pack(side=tk.LEFT, padx=(0,10))
        
        self.cancel_btn = tk.Button(btn_frame, text="Отмена", command=self.cancel_download,
                                  bg="#f44336", fg="white", width=14, font=("Arial", 15, "bold"),
                                  relief="flat", state=tk.DISABLED)
        self.cancel_btn.pack(side=tk.LEFT)
        
        #Прогресс
        self.progress_label = tk.Label(frame, text="", fg="orange", font=("Arial", 15, "bold"))
        self.progress_label.pack(pady=(10,5))
        
        self.progress = ttk.Progressbar(frame, mode='determinate')
        self.progress.pack(fill=tk.X, pady=(0,10))
        
        self.status_label = tk.Label(frame, text="Готов к работе", fg="green", font=("Arial", 15))
        self.status_label.pack(pady=(0,20))
        
        #Восстановление последней папки
        last_folder = self.config.get('paths', 'last_folder', fallback='')
        if last_folder and os.path.exists(last_folder):
            self.folder_path = last_folder
            display_text = f"📁Полный путь сохранения:\n{last_folder}"
            self.folder_label.config(text=display_text, fg="green")
        
        #Обработчики событий
        self.root.bind('<Configure>', self.on_window_resize)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.after(500, self.save_config)
        
        self.log("GUI готов")
        self.root.mainloop()
    
    def choose_folder(self):
        folder = filedialog.askdirectory(title="Выберите папку для сохранения")
        if folder:
            self.folder_path = folder
            display_text = f"📁Полный путь сохранения:\n{folder}"
            self.folder_label.config(text=display_text, fg="green")
            self.save_config()
            self.log(f"Выбрана папка: {folder}")
    
    def on_window_resize(self, event):
        if event.widget == self.root and hasattr(self, 'config'):
            self.root.after_idle(self.save_config)
    
    def on_closing(self):
        self.log("Закрытие приложения")
        self.save_config()
        
        if self.process:
            self.log("Прерывание процесса скачивания")
            self.process.terminate()
            try:
                self.process.wait(timeout=1)
            except:
                self.process.kill()
        
        self.root.destroy()
    
    def find_yt_dlp(self):
        self.log("Поиск yt-dlp")
        paths = [
            os.path.join(os.path.dirname(__file__), "yt-dlp.exe"),
            "yt-dlp.exe",
            os.path.expanduser("~/yt-dlp.exe")
        ]
        for path in paths:
            if os.path.exists(path):
                self.log(f"yt-dlp найден: {path}")
                return path
        try:
            result = subprocess.run(["where", "yt-dlp"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                path = result.stdout.strip().splitlines()[0]
                self.log(f"yt-dlp через PATH: {path}")
                return path
        except Exception as e:
            self.log_error(f"Ошибка поиска yt-dlp: {e}")
        self.log_error("yt-dlp не найден")
        return None
    
    def check_url_availability(self, url, timeout=30):
        self.log_debug(f"Проверка URL: {url}")
        
        if not url.startswith(('http://', 'https://')):
            self.log_error("Неверный формат URL")
            return False
        
        try:
            parsed = urlparse(url)
            if not parsed.netloc:
                self.log_error("Не удалось распарсить URL")
                return False
            
            self.log_debug(f"Тестируем соединение с {parsed.netloc}")
            response = requests.head(url, timeout=timeout, allow_redirects=True)
            self.log(f"URL доступен (код: {response.status_code})")
            return True
            
        except requests.exceptions.Timeout:
            self.log_error(f"Таймаут {timeout}с")
            return False
        except requests.exceptions.ConnectionError:
            self.log_error("Ошибка соединения")
            return False
        except requests.exceptions.RequestException as e:
            self.log_error(f"Ошибка запроса: {e}")
            return False
        except Exception as e:
            self.log_error(f"Неожиданная ошибка: {e}")
            return False
    
    def check_file_exists(self):
        if not self.folder_path:
            return False, None
        url = self.entry.get().strip()
        yt_dlp_path = self.find_yt_dlp()
        if not yt_dlp_path:
            return False, None
        
        self.log("Проверка существования файла")
        cmd = [yt_dlp_path, "--get-filename", "-o", f"{self.folder_path}/%(title)s.%(ext)s",
               "--no-download", "--no-playlist", "-f", "best[height<=1080]", url]
        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            result = subprocess.run(cmd, capture_output=True, text=True, 
                                  timeout=15, cwd=self.folder_path, 
                                  creationflags=0x08000000, startupinfo=startupinfo)
            filename = result.stdout.strip()
            if filename:
                full_path = os.path.join(self.folder_path, filename)
                if os.path.exists(full_path):
                    self.log(f"Файл уже существует: {full_path}")
                    return True, filename
        except Exception as e:
            self.log_error(f"Ошибка проверки файла: {e}")
        return False, None
    
    def download_video(self):
        url = self.entry.get().strip()
        self.log(f"Начало скачивания: {url}")
        
        if not url:
            messagebox.showerror("Ошибка", "Введите ссылку!")
            return
        if not self.folder_path:
            messagebox.showerror("Ошибка", "Выберите папку!")
            return
        
        if not self.check_url_availability(url, timeout=30):
            messagebox.showerror("Ошибка", "Ссылка недоступна или неверная!")
            return
        
        exists, filename = self.check_file_exists()
        if exists:
            result = messagebox.askyesno("Файл существует", 
                f"Файл '{os.path.basename(filename)}' уже есть.\nСоздать дубль '(2)'?")
            if not result:
                return
        
        yt_dlp_path = self.find_yt_dlp()
        if not yt_dlp_path:
            messagebox.showerror("Ошибка", "yt-dlp.exe не найден!\nСкачайте с https://github.com/yt-dlp/yt-dlp")
            return
        
        self.is_cancelled = False
        self.set_ui_downloading(True)
        self.progress['value'] = 0
        self.progress_label.config(text="Запуск...")
        
        cmd = [yt_dlp_path, "-o", f"{self.folder_path}/%(title)s.%(ext)s",
               "--no-playlist", "-f", "best[height<=1080]",
               "--restrict-filenames", "--windows-filenames", "--no-overwrites", url]
        
        self.log(f"Команда: {' '.join(cmd)}")
        
        #Запуск скрытого процесса Windows
        creation_flags = 0x08000000
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        
        self.process = subprocess.Popen(cmd, cwd=self.folder_path,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            universal_newlines=True, bufsize=1,
            creationflags=creation_flags, startupinfo=startupinfo)
        
        threading.Thread(target=self.read_output, daemon=True).start()
    
    def set_ui_downloading(self, downloading):
        state = tk.DISABLED if downloading else tk.NORMAL
        self.download_btn.config(state=state)
        self.cancel_btn.config(state=tk.NORMAL if downloading else tk.DISABLED)
        self.status_label.config(text="⏳ Скачивание..." if downloading else "Готов к работе",
                               fg="orange" if downloading else "green")
    
    def read_output(self):
        try:
            while True:
                line = self.process.stdout.readline()
                if not line or self.is_cancelled:
                    break
                line = line.strip()
                if not line:
                    continue
                
                self.log_debug(f"yt-dlp: {line}")

                #Парсинг процентов
                match = re.search(r'(\d+(?:\.\d+)?)%', line)
                if match:
                    percent = float(match.group(1))
                    self.root.after(0, lambda p=percent: self.update_progress(p, f"📥 {p:.1f}%"))
                
                #Завершение по ключевым словам
                if any(word in line.lower() for word in ['finished', 'downloaded']):
                    self.root.after(0, lambda: self.update_progress(100, "✅Готово!"))
                    self.log("Скачивание завершено успешно")
                    break
        except Exception as e:
            self.log_error(f"Ошибка чтения вывода: {e}")
        finally:
            if self.process:
                self.process.stdout.close()
                try:
                    self.process.wait(timeout=2)
                except:
                    pass
            self.root.after(0, lambda: self.set_ui_downloading(False))
    
    def update_progress(self, percent, text):
        self.progress['value'] = percent
        self.progress_label.config(text=text)
    
    def cancel_download(self):
        self.log("Пользователь отменил скачивание")
        self.is_cancelled = True
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except:
                self.process.kill()
            self.process = None
        self.progress['value'] = 0
        self.progress_label.config(text="⏹ Отменено!")
        self.set_ui_downloading(False)

if __name__ == "__main__":
    RutrackerDownloader()
