# Team Log

## 2026-08-30
- Environment set up on lead laptop (venv, torch CPU, ffmpeg via imageio-ffmpeg)
- Blocks 1-5 done: audio IO, codec simulation, 20 features, toy AI (pipeline proof)
- ASVspoof 2019 LA downloaded + extracted (C:\dhwani_data\LA\LA), manifest verified:
  121,461 rows = official counts exactly
- CNN v1 trained (4,000-clip subset): dev EER 1.2%, eval(unseen) EER 8.5%, TPR@1%FA 98.5%
- Risk engine demoed: honest/sneaky/blatant/glitch scenarios all behave correctly
- Repo: github.com/saaniiyaa/dhavni-kavach (private, collaborators added)
## 2026-08-30 (evening) — BLOCK 8 COMPLETE
Robustness table (eval EER, unseen attacks):
  v1 (clean-trained):    clean 8.5% | mulaw 11.3% | opus16 12.2% | dev 1.2%
  v2 (codec-augmented):  clean 10.7% | mulaw 12.5% | opus16 11.5% | dev 4.5%
Finding: phone codecs cost any detector +3-4 EER points. Naive 50% codec
augmentation did NOT recover the loss at baseline scale (4k clips, small CNN).
Analysis: mel-spectrogram cues are frequency-shape (destroyed by codecs);
the fix is heads built on codec-surviving signals (pitch/jitter/rhythm -
measured surviving in our Block 4 study). This JUSTIFIES the multi-head design.