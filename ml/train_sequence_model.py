"""Optional PyTorch Sequence LSTM Model for NightWatch.

Fuses 14-day longitudinal wearable & home BP time-series sequence vectors
with static EHR demographic embeddings using multimodal concatenation and Focal Loss.
Gracefully degrades with an informational message if PyTorch is not installed.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Optional, Tuple

logger = logging.getLogger("nightwatch.lstm")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torch.utils.data import DataLoader, Dataset
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False


if HAS_TORCH:
    class FocalLoss(nn.Module):
        """Binary Focal Loss to address clinical class imbalance."""

        def __init__(self, alpha: float = 0.25, gamma: float = 2.0) -> None:
            super().__init__()
            self.alpha = alpha
            self.gamma = gamma

        def forward(self, inputs: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
            bce_loss = F.binary_cross_entropy_with_logits(inputs, targets, reduction="none")
            pt = torch.exp(-bce_loss)
            focal_loss = self.alpha * (1 - pt) ** self.gamma * bce_loss
            return focal_loss.mean()

    class MultimodalSequenceTwinModel(nn.Module):
        """Late-fusion deep architecture combining 14-day LSTM wearable state with static EHR embeddings."""

        def __init__(
            self,
            seq_feature_dim: int = 11,
            static_feature_dim: int = 24,
            hidden_dim: int = 64,
            static_embed_dim: int = 32,
            num_layers: int = 2,
            dropout: float = 0.3,
        ) -> None:
            super().__init__()
            # Time-series encoder
            self.lstm = nn.LSTM(
                input_size=seq_feature_dim,
                hidden_size=hidden_dim,
                num_layers=num_layers,
                batch_first=True,
                dropout=dropout if num_layers > 1 else 0.0,
            )
            # Static EHR encoder
            self.static_net = nn.Sequential(
                nn.Linear(static_feature_dim, static_embed_dim),
                nn.ReLU(),
                nn.Dropout(dropout),
            )
            # Multimodal fusion classifier
            fusion_dim = hidden_dim + static_embed_dim
            self.classifier = nn.Sequential(
                nn.Linear(fusion_dim, 32),
                nn.ReLU(),
                nn.Dropout(dropout),
                nn.Linear(32, 1),
            )

        def forward(self, x_seq: torch.Tensor, x_static: torch.Tensor) -> torch.Tensor:
            _, (h_n, _) = self.lstm(x_seq)
            lstm_out = h_n[-1]  # Last layer hidden state
            static_out = self.static_net(x_static)
            fused = torch.cat([lstm_out, static_out], dim=1)
            logits = self.classifier(fused)
            return logits.squeeze(-1)


def train_sequence_model(
    epochs: int = 15,
    batch_size: int = 64,
    learning_rate: float = 1e-3,
    artifacts_dir: str = "ml/artifacts",
) -> None:
    """Train the PyTorch LSTM sequence model if PyTorch is installed."""
    if not HAS_TORCH:
        logger.info(
            "PyTorch is not installed in the current environment. "
            "Skipping optional sequence model training. "
            "The production NightWatch application uses calibrated LightGBM by default."
        )
        return

    logger.info("Initializing NightWatch PyTorch Multimodal Sequence LSTM training...")
    os.makedirs(artifacts_dir, exist_ok=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"Using computing device: {device}")

    # Synthetic demo training loop
    model = MultimodalSequenceTwinModel().to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=1e-4)
    criterion = FocalLoss(alpha=0.30, gamma=2.0)

    # Simulated tensor batch to demonstrate forward and backward convergence
    torch.manual_seed(42)
    dummy_seq = torch.randn(128, 14, 11).to(device)
    dummy_static = torch.randn(128, 24).to(device)
    dummy_labels = (torch.rand(128) > 0.75).float().to(device)

    model.train()
    for ep in range(epochs):
        optimizer.zero_grad()
        out = model(dummy_seq, dummy_static)
        loss = criterion(out, dummy_labels)
        loss.backward()
        optimizer.step()
        if (ep + 1) % 5 == 0:
            logger.info(f"Epoch [{ep+1}/{epochs}] - Loss: {loss.item():.4f}")

    checkpoint_path = os.path.join(artifacts_dir, "sequence_lstm_model.pt")
    torch.save(model.state_dict(), checkpoint_path)
    logger.info(f"Saved PyTorch sequence model checkpoint to {checkpoint_path}")


if __name__ == "__main__":
    train_sequence_model()
