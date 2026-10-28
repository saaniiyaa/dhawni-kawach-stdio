import sys
import numpy
import scipy
import librosa
import soundfile
import sklearn
import torch
import imageio_ffmpeg

print("python     :", sys.version.split()[0])
print("numpy      :", numpy.__version__)
print("librosa    :", librosa.__version__)
print("torch      :", torch.__version__)
print("ffmpeg here:", imageio_ffmpeg.get_ffmpeg_exe())
print()
print("SETUP OK")