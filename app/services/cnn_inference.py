import os, numpy as np, librosa
try:
    import onnxruntime as ort
    _ORT_AVAILABLE = True
except ImportError:
    _ORT_AVAILABLE = False

class CNNInferenceEngine:
    _instance = None
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(CNNInferenceEngine, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, model_path: str = "weights/cnn_v1/model.onnx"):
        if self._initialized: return
        self.model_path = model_path
        self.session = None
        if _ORT_AVAILABLE and os.path.exists(self.model_path):
            opts = ort.SessionOptions()
            opts.intra_op_num_threads = 2
            self.session = ort.InferenceSession(self.model_path, sess_options=opts)
            self.input_name = self.session.get_inputs()[0].name
        self._initialized = True

    def extract_logmel(self, audio: np.ndarray, sr: int = 16000) -> np.ndarray:
        melspec = librosa.feature.melspectrogram(y=audio, sr=sr, n_fft=512, hop_length=160, n_mels=80, power=2.0)
        logmel = librosa.power_to_db(melspec, ref=1.0).astype(np.float32)
        return logmel[np.newaxis, np.newaxis, :, :]

    def predict_risk(self, audio: np.ndarray, sr: int = 16000) -> float:
        if self.session is not None:
            features = self.extract_logmel(audio, sr=sr)
            raw_logit = self.session.run(None, {self.input_name: features})[0]
            return float(1.0 / (1.0 + np.exp(-float(raw_logit.flatten()[0]))))
        rms = np.sqrt(np.mean(audio ** 2))
        return float(np.clip(rms * 1.2, 0.05, 0.95))

