# === Standard Library Imports ===
import os
import json
import time
import pandas as pd

# === PyTorch Core Imports ===
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, random_split
from torch.nn.utils.rnn import pad_sequence

# === Custom Modules ===
from src.dataset import DietDataset
from src.model import Encoder, Decoder, Seq2Seq

# === Dummy Data Creator ===
def create_dummy_approved_plans():
    print("🔧 Creating a dummy 'approved_plans.csv' for demonstration...")
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    bootstrap_path = os.path.join(SCRIPT_DIR, 'data', '1_bootstrap_training_data.csv')
    approved_path = os.path.join(SCRIPT_DIR, 'data', 'approved_plans.csv')

    if not os.path.exists(bootstrap_path):
        print("❌ ERROR: '1_bootstrap_training_data.csv' not found.")
        return

    bootstrap_data = pd.read_csv(bootstrap_path).sample(10)
    bootstrap_data.to_csv(approved_path, index=False)
    print("✅ Dummy approved data created.")

# === Collate Function ===
def collate_fn(batch):
    user_vectors, plan_sequences = zip(*batch)
    user_vectors = torch.stack(user_vectors)
    plan_sequences_padded = pad_sequence(plan_sequences, batch_first=False, padding_value=0)
    return user_vectors, plan_sequences_padded

# === Hyperparameters & Paths ===
INPUT_DIM = 21
ENC_EMB_DIM = 256
DEC_EMB_DIM = 256
HID_DIM = 512
N_EPOCHS = 15
CLIP = 1
BATCH_SIZE = 8
LEARNING_RATE = 1e-4
VAL_SPLIT = 0.2

DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

VOCAB_PATH = os.path.join(SCRIPT_DIR, 'saved_models', 'food_vocab.json')
MODEL_SAVE_PATH = os.path.join(SCRIPT_DIR, 'saved_models', 'diet_model_v2.pth')
CHECKPOINT_PATH = os.path.join(SCRIPT_DIR, 'saved_models', 'diet_model_v2_checkpoint.pth')
V1_MODEL_PATH = os.path.join(SCRIPT_DIR, 'saved_models', 'diet_model_v1_epoch_79.pth')
APPROVED_PLANS_PATH = os.path.join(SCRIPT_DIR, 'data', 'approved_plans.csv')

# === Validation Function ===
@torch.no_grad()
def validate(model, val_loader, criterion):
    model.eval()
    val_loss = 0
    for user_vectors, plan_sequences in val_loader:
        src = user_vectors.to(DEVICE)
        trg = plan_sequences.to(DEVICE)

        output = model(src, trg, teacher_forcing_ratio=0.0)
        output_dim = output.shape[-1]
        output = output[1:].view(-1, output_dim)
        trg = trg[1:].view(-1)

        loss = criterion(output, trg)
        val_loss += loss.item()
    return val_loss / len(val_loader)

# === Main Training Function ===
def retrain():
    print(f"🚀 Starting retraining on {DEVICE}...")
    start_time = time.time()

    if not os.path.exists(VOCAB_PATH):
        raise FileNotFoundError(f"❌ Vocabulary file not found at {VOCAB_PATH}.")
    OUTPUT_DIM = len(json.load(open(VOCAB_PATH)))

    if not os.path.exists(APPROVED_PLANS_PATH):
        create_dummy_approved_plans()
    if not os.path.exists(APPROVED_PLANS_PATH):
        return

    dataset = DietDataset(APPROVED_PLANS_PATH)

    # === Split into Train/Val ===
    val_size = int(len(dataset) * VAL_SPLIT)
    train_size = len(dataset) - val_size
    train_dataset, val_dataset = random_split(dataset, [train_size, val_size])

    train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True, collate_fn=collate_fn)
    val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE, shuffle=False, collate_fn=collate_fn)

    encoder = Encoder(INPUT_DIM, ENC_EMB_DIM, HID_DIM)
    decoder = Decoder(OUTPUT_DIM, DEC_EMB_DIM, HID_DIM)
    model = Seq2Seq(encoder, decoder, DEVICE).to(DEVICE)

    if not os.path.exists(V1_MODEL_PATH):
        print(f"❌ ERROR: Pre-trained model not found at {V1_MODEL_PATH}.")
        return

    checkpoint = torch.load(V1_MODEL_PATH, map_location=DEVICE)
    model.load_state_dict(checkpoint['model_state_dict'])
    print("✅ Loaded pre-trained V1 model.")

    optimizer = optim.Adam(model.parameters(), lr=LEARNING_RATE)
    PAD_IDX = 0
    criterion = nn.CrossEntropyLoss(ignore_index=PAD_IDX)

    model.train()
    for epoch in range(1, N_EPOCHS + 1):
        epoch_start = time.time()
        epoch_loss = 0

        for user_vectors, plan_sequences in train_loader:
            src = user_vectors.to(DEVICE)
            trg = plan_sequences.to(DEVICE)

            optimizer.zero_grad()
            output = model(src, trg, teacher_forcing_ratio=0.7)

            output_dim = output.shape[-1]
            output = output[1:].view(-1, output_dim)
            trg = trg[1:].view(-1)

            loss = criterion(output, trg)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), CLIP)
            optimizer.step()
            epoch_loss += loss.item()

        avg_train_loss = epoch_loss / len(train_loader)
        avg_val_loss = validate(model, val_loader, criterion)
        print(f"📚 Epoch {epoch:02} | Train Loss: {avg_train_loss:.4f} | Val Loss: {avg_val_loss:.4f} | Time: {time.time() - epoch_start:.2f}s")

        # === Save checkpoint ===
        torch.save({
            'epoch': epoch,
            'model_state_dict': model.state_dict(),
            'optimizer_state_dict': optimizer.state_dict(),
            'train_loss': avg_train_loss,
            'val_loss': avg_val_loss,
        }, CHECKPOINT_PATH)

    torch.save(model.state_dict(), MODEL_SAVE_PATH)
    print(f"\n✅ Retraining complete. Final model saved as '{MODEL_SAVE_PATH}'.")
    print(f"⏱️ Total training time: {time.time() - start_time:.2f} seconds")

# === Run if script is main ===
if __name__ == '__main__':
    retrain()
