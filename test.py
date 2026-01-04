"""
Vertex AI 번역 프로그램
- Google Vertex AI API를 사용한 번역
- 서비스 계정 키 파일로 인증
- 모델 선택 가능
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import json
import urllib.request
import urllib.error
import urllib.parse
import base64
import hashlib
import time
from pathlib import Path


def base64url_encode(data: bytes) -> str:
    """Base64 URL-safe 인코딩"""
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')


def rsa_sign(message: bytes, private_key_pem: str) -> bytes:
    """RSA SHA256 서명 (순수 Python 구현)"""
    # PEM에서 DER 추출
    lines = private_key_pem.strip().split('\n')
    der_b64 = ''.join(line for line in lines if not line.startswith('-----'))
    der = base64.b64decode(der_b64)
    
    # DER에서 private key 파싱 (PKCS#8 형식)
    def parse_asn1(data, offset=0):
        tag = data[offset]
        length = data[offset + 1]
        if length & 0x80:
            num_bytes = length & 0x7f
            length = int.from_bytes(data[offset + 2:offset + 2 + num_bytes], 'big')
            offset += 2 + num_bytes
        else:
            offset += 2
        return tag, length, offset
    
    def extract_integer(data, offset):
        tag, length, start = parse_asn1(data, offset)
        value = int.from_bytes(data[start:start + length], 'big')
        return value, start + length
    
    # PKCS#8 구조 파싱
    offset = 0
    tag, length, offset = parse_asn1(der, offset)  # SEQUENCE
    tag, length, offset = parse_asn1(der, offset)  # INTEGER (version)
    offset += length
    tag, length, offset = parse_asn1(der, offset)  # SEQUENCE (algorithm)
    offset += length
    tag, length, offset = parse_asn1(der, offset)  # OCTET STRING (privateKey)
    
    # RSA private key (PKCS#1)
    inner_der = der[offset:offset + length]
    offset = 0
    tag, length, offset = parse_asn1(inner_der, offset)  # SEQUENCE
    
    version, offset = extract_integer(inner_der, offset)
    n, offset = extract_integer(inner_der, offset)  # modulus
    e, offset = extract_integer(inner_der, offset)  # publicExponent
    d, offset = extract_integer(inner_der, offset)  # privateExponent
    
    # SHA256 해시
    sha256_hash = hashlib.sha256(message).digest()
    
    # PKCS#1 v1.5 패딩 - DigestInfo for SHA256
    digest_info = bytes([
        0x30, 0x31, 0x30, 0x0d, 0x06, 0x09, 0x60, 0x86,
        0x48, 0x01, 0x65, 0x03, 0x04, 0x02, 0x01, 0x05,
        0x00, 0x04, 0x20
    ]) + sha256_hash
    
    # 키 크기 (바이트)
    k = (n.bit_length() + 7) // 8
    
    # 패딩: 0x00 0x01 [0xff padding] 0x00 [digest_info]
    ps_len = k - len(digest_info) - 3
    padded = b'\x00\x01' + (b'\xff' * ps_len) + b'\x00' + digest_info
    
    # 정수로 변환
    m = int.from_bytes(padded, 'big')
    
    # RSA 서명: s = m^d mod n
    s = pow(m, d, n)
    
    return s.to_bytes(k, 'big')


def create_jwt(service_account_info: dict) -> str:
    """서비스 계정 정보로 JWT 토큰 생성"""
    header = {"alg": "RS256", "typ": "JWT"}
    
    now = int(time.time())
    payload = {
        "iss": service_account_info["client_email"],
        "sub": service_account_info["client_email"],
        "aud": "https://oauth2.googleapis.com/token",
        "iat": now,
        "exp": now + 3600,
        "scope": "https://www.googleapis.com/auth/cloud-platform"
    }
    
    header_b64 = base64url_encode(json.dumps(header).encode('utf-8'))
    payload_b64 = base64url_encode(json.dumps(payload).encode('utf-8'))
    signing_input = f"{header_b64}.{payload_b64}"
    
    private_key_pem = service_account_info["private_key"]
    signature = rsa_sign(signing_input.encode('utf-8'), private_key_pem)
    signature_b64 = base64url_encode(signature)
    
    return f"{signing_input}.{signature_b64}"


def get_access_token(service_account_info: dict) -> str:
    """서비스 계정으로 액세스 토큰 획득"""
    jwt_token = create_jwt(service_account_info)
    
    url = "https://oauth2.googleapis.com/token"
    data = urllib.parse.urlencode({
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": jwt_token
    }).encode('utf-8')
    
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    
    with urllib.request.urlopen(req, timeout=30) as response:
        result = json.loads(response.read().decode('utf-8'))
        return result["access_token"]


class Settings:
    """설정 관리 클래스"""
    
    CONFIG_FILE = Path(__file__).parent / "translator_config.json"
    
    DEFAULT_SETTINGS = {
        "service_account_path": "",
        "project_id": "",
        "location": "us-central1",
        "model": "gemini-2.5-flash-preview-05-20",
        "source_lang": "자동 감지",
        "target_lang": "한국어"
    }
    
    AVAILABLE_MODELS = [
        "gemini-2.5-flash-preview-05-20",
        "gemini-2.0-flash-001",
        "gemini-1.5-flash-002",
        "gemini-1.5-pro-002",
    ]
    
    LANGUAGES = [
        "자동 감지", "한국어", "영어", "일본어", "중국어(간체)", 
        "중국어(번체)", "스페인어", "프랑스어", "독일어", 
        "러시아어", "포르투갈어", "이탈리아어", "베트남어", "태국어"
    ]
    
    def __init__(self):
        self.settings = self.load()
        self._access_token = None
        self._token_expiry = 0
    
    def load(self) -> dict:
        """설정 파일 로드"""
        try:
            if self.CONFIG_FILE.exists():
                with open(self.CONFIG_FILE, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    return {**self.DEFAULT_SETTINGS, **loaded}
        except Exception as e:
            print(f"설정 로드 오류: {e}")
        return self.DEFAULT_SETTINGS.copy()
    
    def save(self) -> bool:
        """설정 파일 저장"""
        try:
            with open(self.CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"설정 저장 오류: {e}")
            return False
    
    def get(self, key: str, default=None):
        return self.settings.get(key, default)
    
    def set(self, key: str, value):
        self.settings[key] = value
    
    def get_service_account_info(self) -> dict:
        """서비스 계정 정보 로드"""
        path = self.get("service_account_path")
        if not path or not Path(path).exists():
            raise ValueError("서비스 계정 키 파일이 설정되지 않았습니다.")
        
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def get_access_token(self) -> str:
        """액세스 토큰 획득 (캐싱)"""
        now = time.time()
        if self._access_token and now < self._token_expiry - 60:
            return self._access_token
        
        service_account_info = self.get_service_account_info()
        self._access_token = get_access_token(service_account_info)
        self._token_expiry = now + 3600
        return self._access_token


class VertexAITranslator:
    """Vertex AI API를 사용한 번역기"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
    
    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """텍스트 번역"""
        project_id = self.settings.get("project_id")
        location = self.settings.get("location")
        model = self.settings.get("model")
        
        if not project_id:
            raise ValueError("프로젝트 ID가 설정되지 않았습니다.")
        
        if not text.strip():
            raise ValueError("번역할 텍스트를 입력해주세요.")
        
        # 액세스 토큰 획득
        access_token = self.settings.get_access_token()
        
        # 프롬프트 생성
        if source_lang == "자동 감지":
            prompt = f"다음 텍스트를 {target_lang}로 번역해주세요. 번역 결과만 출력하고 다른 설명은 하지 마세요.\n\n{text}"
        else:
            prompt = f"다음 {source_lang} 텍스트를 {target_lang}로 번역해주세요. 번역 결과만 출력하고 다른 설명은 하지 마세요.\n\n{text}"
        
        # Vertex AI API 엔드포인트
        url = f"https://{location}-aiplatform.googleapis.com/v1/projects/{project_id}/locations/{location}/publishers/google/models/{model}:generateContent"
        
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 8192
            }
        }
        
        data = json.dumps(payload).encode("utf-8")
        
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}"
            },
            method="POST"
        )
        
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                result = json.loads(response.read().decode("utf-8"))
                
                candidates = result.get("candidates", [])
                if candidates:
                    content = candidates[0].get("content", {})
                    parts = content.get("parts", [])
                    if parts:
                        return parts[0].get("text", "").strip()
                
                raise ValueError("번역 결과를 가져올 수 없습니다.")
                
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8")
            try:
                error_json = json.loads(error_body)
                error_msg = error_json.get("error", {}).get("message", str(e))
            except:
                error_msg = error_body or str(e)
            raise ValueError(f"API 오류 ({e.code}): {error_msg}")
        except urllib.error.URLError as e:
            raise ValueError(f"네트워크 오류: {e.reason}")


class SettingsWindow(tk.Toplevel):
    """설정 창"""
    
    def __init__(self, parent, settings: Settings):
        super().__init__(parent)
        self.settings = settings
        self.title("Vertex AI 설정")
        self.geometry("550x480")
        self.resizable(False, False)
        
        self.transient(parent)
        self.grab_set()
        
        self.create_widgets()
        self.load_current_settings()
        
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
    
    def create_widgets(self):
        """위젯 생성"""
        main_frame = ttk.Frame(self, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 서비스 계정 키 파일
        ttk.Label(main_frame, text="서비스 계정 키 파일 (JSON):").pack(anchor=tk.W)
        
        key_frame = ttk.Frame(main_frame)
        key_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.service_account_var = tk.StringVar()
        ttk.Entry(key_frame, textvariable=self.service_account_var, width=50).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(key_frame, text="찾아보기", command=self.browse_key_file).pack(side=tk.RIGHT, padx=(5, 0))
        
        # 프로젝트 ID
        ttk.Label(main_frame, text="프로젝트 ID:").pack(anchor=tk.W)
        self.project_id_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.project_id_var, width=50).pack(fill=tk.X, pady=(0, 10))
        
        # 위치 (Region)
        ttk.Label(main_frame, text="위치 (Region):").pack(anchor=tk.W)
        self.location_var = tk.StringVar()
        ttk.Combobox(
            main_frame,
            textvariable=self.location_var,
            values=["us-central1", "asia-northeast1", "asia-northeast3", "europe-west1"],
            width=30
        ).pack(anchor=tk.W, pady=(0, 10))
        
        # 모델 선택
        ttk.Label(main_frame, text="기본 모델:").pack(anchor=tk.W)
        self.model_var = tk.StringVar()
        ttk.Combobox(
            main_frame, 
            textvariable=self.model_var, 
            values=Settings.AVAILABLE_MODELS,
            state="readonly",
            width=40
        ).pack(fill=tk.X, pady=(0, 10))
        
        # 모델 설명
        ttk.Label(
            main_frame, 
            text="※ gemini-2.5-flash-preview: 최신 | gemini-1.5-pro: 고품질",
            foreground="gray"
        ).pack(anchor=tk.W, pady=(0, 15))
        
        # 기본 언어 설정
        lang_frame = ttk.LabelFrame(main_frame, text="기본 언어 설정", padding=10)
        lang_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Label(lang_frame, text="원본 언어:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.source_lang_var = tk.StringVar()
        ttk.Combobox(
            lang_frame, 
            textvariable=self.source_lang_var, 
            values=Settings.LANGUAGES,
            state="readonly",
            width=20
        ).grid(row=0, column=1, sticky=tk.W)
        
        ttk.Label(lang_frame, text="대상 언어:").grid(row=1, column=0, sticky=tk.W, padx=(0, 10), pady=(10, 0))
        self.target_lang_var = tk.StringVar()
        ttk.Combobox(
            lang_frame, 
            textvariable=self.target_lang_var, 
            values=Settings.LANGUAGES[1:],
            state="readonly",
            width=20
        ).grid(row=1, column=1, sticky=tk.W, pady=(10, 0))
        
        # 버튼
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(btn_frame, text="저장", command=self.save_settings, width=15).pack(side=tk.RIGHT, padx=(10, 0))
        ttk.Button(btn_frame, text="취소", command=self.destroy, width=15).pack(side=tk.RIGHT)
        
        # 안내
        ttk.Label(
            main_frame,
            text="💡 서비스 계정 키는 Google Cloud Console에서 발급받을 수 있습니다.\n   IAM > 서비스 계정 > 키 만들기 (JSON)",
            foreground="blue"
        ).pack(anchor=tk.W, pady=(15, 0))
    
    def browse_key_file(self):
        """키 파일 찾아보기"""
        filepath = filedialog.askopenfilename(
            title="서비스 계정 키 파일 선택",
            filetypes=[("JSON 파일", "*.json"), ("모든 파일", "*.*")],
            parent=self
        )
        if filepath:
            self.service_account_var.set(filepath)
            # 키 파일에서 프로젝트 ID 자동 추출
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if "project_id" in data and not self.project_id_var.get():
                        self.project_id_var.set(data["project_id"])
            except:
                pass
    
    def load_current_settings(self):
        """현재 설정 로드"""
        self.service_account_var.set(self.settings.get("service_account_path", ""))
        self.project_id_var.set(self.settings.get("project_id", ""))
        self.location_var.set(self.settings.get("location", "us-central1"))
        self.model_var.set(self.settings.get("model", "gemini-2.5-flash-preview-05-20"))
        self.source_lang_var.set(self.settings.get("source_lang", "자동 감지"))
        self.target_lang_var.set(self.settings.get("target_lang", "한국어"))
    
    def save_settings(self):
        """설정 저장"""
        service_account_path = self.service_account_var.get().strip()
        project_id = self.project_id_var.get().strip()
        
        if not service_account_path:
            messagebox.showwarning("경고", "서비스 계정 키 파일을 선택해주세요.", parent=self)
            return
        
        if not Path(service_account_path).exists():
            messagebox.showwarning("경고", "서비스 계정 키 파일이 존재하지 않습니다.", parent=self)
            return
        
        if not project_id:
            messagebox.showwarning("경고", "프로젝트 ID를 입력해주세요.", parent=self)
            return
        
        self.settings.set("service_account_path", service_account_path)
        self.settings.set("project_id", project_id)
        self.settings.set("location", self.location_var.get())
        self.settings.set("model", self.model_var.get())
        self.settings.set("source_lang", self.source_lang_var.get())
        self.settings.set("target_lang", self.target_lang_var.get())
        
        # 토큰 캐시 초기화
        self.settings._access_token = None
        self.settings._token_expiry = 0
        
        if self.settings.save():
            messagebox.showinfo("알림", "설정이 저장되었습니다.", parent=self)
            self.destroy()
        else:
            messagebox.showerror("오류", "설정 저장에 실패했습니다.", parent=self)


class TranslatorApp(tk.Tk):
    """메인 번역 애플리케이션"""
    
    def __init__(self):
        super().__init__()
        
        self.title("Vertex AI 번역기")
        self.geometry("900x600")
        self.minsize(700, 500)
        
        self.settings = Settings()
        self.translator = VertexAITranslator(self.settings)
        
        self.create_menu()
        self.create_widgets()
        
        self.bind("<Control-Return>", lambda e: self.translate())
        self.bind("<Control-s>", lambda e: self.open_settings())
    
    def create_menu(self):
        """메뉴 생성"""
        menubar = tk.Menu(self)
        self.config(menu=menubar)
        
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="파일", menu=file_menu)
        file_menu.add_command(label="설정", command=self.open_settings, accelerator="Ctrl+S")
        file_menu.add_separator()
        file_menu.add_command(label="종료", command=self.quit)
        
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="도움말", menu=help_menu)
        help_menu.add_command(label="사용 방법", command=self.show_help)
    
    def create_widgets(self):
        """위젯 생성"""
        # 상단 컨트롤 바
        control_frame = ttk.Frame(self, padding=10)
        control_frame.pack(fill=tk.X)
        
        # 원본 언어 선택
        ttk.Label(control_frame, text="원본:").pack(side=tk.LEFT)
        self.source_lang_var = tk.StringVar(value=self.settings.get("source_lang", "자동 감지"))
        ttk.Combobox(
            control_frame, 
            textvariable=self.source_lang_var, 
            values=Settings.LANGUAGES,
            state="readonly",
            width=12
        ).pack(side=tk.LEFT, padx=(5, 15))
        
        # 언어 교환 버튼
        ttk.Button(control_frame, text="⇄", command=self.swap_languages, width=3).pack(side=tk.LEFT, padx=(0, 15))
        
        # 대상 언어 선택
        ttk.Label(control_frame, text="대상:").pack(side=tk.LEFT)
        self.target_lang_var = tk.StringVar(value=self.settings.get("target_lang", "한국어"))
        ttk.Combobox(
            control_frame, 
            textvariable=self.target_lang_var, 
            values=Settings.LANGUAGES[1:],
            state="readonly",
            width=12
        ).pack(side=tk.LEFT, padx=(5, 15))
        
        # 모델 선택
        ttk.Label(control_frame, text="모델:").pack(side=tk.LEFT, padx=(20, 0))
        self.model_var = tk.StringVar(value=self.settings.get("model", "gemini-2.5-flash-preview-05-20"))
        ttk.Combobox(
            control_frame, 
            textvariable=self.model_var, 
            values=Settings.AVAILABLE_MODELS,
            state="readonly",
            width=25
        ).pack(side=tk.LEFT, padx=(5, 0))
        
        # 설정 버튼
        ttk.Button(control_frame, text="⚙ 설정", command=self.open_settings).pack(side=tk.RIGHT)
        
        # 텍스트 영역 프레임
        text_frame = ttk.Frame(self, padding=10)
        text_frame.pack(fill=tk.BOTH, expand=True)
        
        # 왼쪽: 입력 영역 (30%)
        input_frame = ttk.LabelFrame(text_frame, text="원본 텍스트", padding=5)
        input_frame.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 5))
        input_frame.configure(width=280)
        
        self.input_text = scrolledtext.ScrolledText(
            input_frame, 
            wrap=tk.WORD, 
            font=("맑은 고딕", 11),
            width=30,
            undo=True
        )
        self.input_text.pack(fill=tk.BOTH, expand=True)
        input_frame.pack_propagate(False)
        
        # 입력 영역 버튼
        input_btn_frame = ttk.Frame(input_frame)
        input_btn_frame.pack(fill=tk.X, pady=(5, 0))
        ttk.Button(input_btn_frame, text="지우기", command=self.clear_input).pack(side=tk.LEFT)
        ttk.Button(input_btn_frame, text="붙여넣기", command=self.paste_input).pack(side=tk.LEFT, padx=(5, 0))
        
        # 오른쪽: 출력 영역 (70%)
        output_frame = ttk.LabelFrame(text_frame, text="번역 결과", padding=5)
        output_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        self.output_text = scrolledtext.ScrolledText(
            output_frame, 
            wrap=tk.WORD, 
            font=("맑은 고딕", 11),
            state=tk.DISABLED
        )
        self.output_text.pack(fill=tk.BOTH, expand=True)
        
        # 출력 영역 버튼
        output_btn_frame = ttk.Frame(output_frame)
        output_btn_frame.pack(fill=tk.X, pady=(5, 0))
        ttk.Button(output_btn_frame, text="복사", command=self.copy_output).pack(side=tk.LEFT)
        
        # 하단 버튼 프레임
        bottom_frame = ttk.Frame(self, padding=10)
        bottom_frame.pack(fill=tk.X)
        
        # 번역 버튼
        self.translate_btn = ttk.Button(
            bottom_frame, 
            text="번역하기 (Ctrl+Enter)", 
            command=self.translate
        )
        self.translate_btn.pack(side=tk.RIGHT)
        
        # 상태 표시줄
        self.status_var = tk.StringVar(value="준비됨")
        ttk.Label(bottom_frame, textvariable=self.status_var, foreground="gray").pack(side=tk.LEFT)
    
    def translate(self):
        """번역 실행"""
        text = self.input_text.get("1.0", tk.END).strip()
        
        if not text:
            messagebox.showwarning("경고", "번역할 텍스트를 입력해주세요.")
            return
        
        # 설정 확인
        if not self.settings.get("service_account_path"):
            if messagebox.askyesno("알림", "서비스 계정이 설정되지 않았습니다.\n설정 창을 열까요?"):
                self.open_settings()
            return
        
        self.translate_btn.config(state=tk.DISABLED)
        self.status_var.set("번역 중...")
        self.update()
        
        # 선택된 모델 설정에 반영
        self.settings.set("model", self.model_var.get())
        
        try:
            result = self.translator.translate(
                text, 
                self.source_lang_var.get(), 
                self.target_lang_var.get()
            )
            
            self.output_text.config(state=tk.NORMAL)
            self.output_text.delete("1.0", tk.END)
            self.output_text.insert("1.0", result)
            self.output_text.config(state=tk.DISABLED)
            
            self.status_var.set(f"번역 완료 (모델: {self.model_var.get()})")
            
        except Exception as e:
            messagebox.showerror("오류", str(e))
            self.status_var.set("오류 발생")
        
        finally:
            self.translate_btn.config(state=tk.NORMAL)
    
    def swap_languages(self):
        """원본/대상 언어 교환"""
        source = self.source_lang_var.get()
        target = self.target_lang_var.get()
        
        if source == "자동 감지":
            messagebox.showinfo("알림", "'자동 감지'는 교환할 수 없습니다.")
            return
        
        self.source_lang_var.set(target)
        self.target_lang_var.set(source)
        
        input_text = self.input_text.get("1.0", tk.END).strip()
        output_text = self.output_text.get("1.0", tk.END).strip()
        
        if output_text:
            self.input_text.delete("1.0", tk.END)
            self.input_text.insert("1.0", output_text)
            
            self.output_text.config(state=tk.NORMAL)
            self.output_text.delete("1.0", tk.END)
            self.output_text.insert("1.0", input_text)
            self.output_text.config(state=tk.DISABLED)
    
    def clear_input(self):
        self.input_text.delete("1.0", tk.END)
    
    def paste_input(self):
        try:
            text = self.clipboard_get()
            self.input_text.insert(tk.INSERT, text)
        except tk.TclError:
            pass
    
    def copy_output(self):
        text = self.output_text.get("1.0", tk.END).strip()
        if text:
            self.clipboard_clear()
            self.clipboard_append(text)
            self.status_var.set("클립보드에 복사됨")
    
    def open_settings(self):
        SettingsWindow(self, self.settings)
        self.model_var.set(self.settings.get("model", "gemini-2.5-flash-preview-05-20"))
        self.source_lang_var.set(self.settings.get("source_lang", "자동 감지"))
        self.target_lang_var.set(self.settings.get("target_lang", "한국어"))
    
    def show_help(self):
        help_text = """
Vertex AI 번역기 사용 방법

1. Google Cloud Console에서 서비스 계정을 만들고 키(JSON)를 다운로드하세요.
   - IAM 및 관리자 > 서비스 계정 > 서비스 계정 만들기
   - 키 만들기 > JSON 형식으로 다운로드

2. 서비스 계정에 Vertex AI 사용 권한을 부여하세요.
   - roles/aiplatform.user 역할 필요

3. 설정에서 서비스 계정 키 파일, 프로젝트 ID, 위치를 입력하세요.

4. 번역할 텍스트를 입력하고 '번역하기' 버튼을 클릭하세요.

단축키:
- Ctrl+Enter: 번역 실행
- Ctrl+S: 설정 열기

사용 가능한 모델:
- gemini-2.5-flash-preview-05-20: 최신 모델
- gemini-2.0-flash-001: 빠른 응답
- gemini-1.5-flash-002: 안정적
- gemini-1.5-pro-002: 높은 품질
        """
        messagebox.showinfo("사용 방법", help_text.strip())


if __name__ == "__main__":
    app = TranslatorApp()
    app.mainloop()
