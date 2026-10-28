# ml/models/cnn.py
# H2: log-mel CNN with squeeze-excitation. Deliberately small:
#  * trains on a CPU in minutes, so the whole team can iterate
#  * gives us Grad-CAM later (visual explanation for the UI)
#  * the honest baseline that bigger models must beat

import torch, torch.nn as nn, torch.nn.functional as F


class SE(nn.Module):
    """Squeeze-excitation: the network learns WHICH frequency bands matter."""
    def __init__(self, c, r=8):
        super().__init__()
        self.fc1, self.fc2 = nn.Linear(c, max(c // r, 4)), nn.Linear(max(c // r, 4), c)

    def forward(self, x):
        s = x.mean(dim=(2, 3))
        s = torch.sigmoid(self.fc2(F.relu(self.fc1(s))))
        return x * s[:, :, None, None]


class Block(nn.Module):
    def __init__(self, cin, cout, stride=2):
        super().__init__()
        self.c1 = nn.Conv2d(cin, cout, 3, stride, 1, bias=False)
        self.b1 = nn.BatchNorm2d(cout)
        self.c2 = nn.Conv2d(cout, cout, 3, 1, 1, bias=False)
        self.b2 = nn.BatchNorm2d(cout)
        self.se = SE(cout)
        self.sc = nn.Sequential() if (stride == 1 and cin == cout) else nn.Sequential(
            nn.Conv2d(cin, cout, 1, stride, bias=False), nn.BatchNorm2d(cout))

    def forward(self, x):
        h = F.relu(self.b1(self.c1(x)))
        h = self.se(self.b2(self.c2(h)))
        return F.relu(h + self.sc(x))


class MelCNN(nn.Module):
    def __init__(self, widths=(16, 32, 64, 96), dropout=0.3):
        super().__init__()
        layers, cin = [], 1
        for w in widths:
            layers.append(Block(cin, w)); cin = w
        self.body = nn.Sequential(*layers)
        self.last_channels = cin
        self.head = nn.Sequential(nn.Dropout(dropout), nn.Linear(cin * 2, 64),
                                  nn.ReLU(), nn.Dropout(dropout), nn.Linear(64, 1))
        self._feat = None

    def features(self, x):
        return self.body(x)

    def forward(self, x):
        h = self.body(x)
        self._feat = h
        mean = h.mean(dim=(2, 3)); std = h.std(dim=(2, 3))
        return self.head(torch.cat([mean, std], dim=1)).squeeze(1)   # logit


@torch.no_grad()
def count_params(m):
    return sum(p.numel() for p in m.parameters())