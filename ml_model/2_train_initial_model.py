# ======================================================================================
# 🔹 Import Required Libraries
# ======================================================================================
import torch  # Main PyTorch library
import torch.nn as nn  # Neural network building blocks (like LSTM, Linear, etc.)
import torch.optim as optim  # Optimizers (e.g., Adam)
from torch.utils.data import DataLoader, random_split  # For batching and train/val split
from torch.nn.utils.rnn import pad_sequence  # To handle variable-length sequences

from src.dataset import DietDataset  # Custom dataset class that loads user/plan data
from src.model import Encoder, Decoder, Seq2Seq  # Your model components

import json  # To read vocab file
import os  # For file/directory operations
import time  # For measuring training time

# ======================================================================================
# 🔹 Safety setting: Disable CUDNN backend if using CPU to avoid unexpected crashes
# ======================================================================================
torch.backends.cudnn.enabled = False

# ======================================================================================
# 🔹 File Paths Configuration
# ======================================================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))  # Current script's directory
VOCAB_PATH = os.path.join(SCRIPT_DIR, 'saved_models', 'food_vocab.json')  # Food vocab
MODEL_SAVE_PATH = os.path.join(SCRIPT_DIR, 'saved_models', 'diet_model_v1.pth')  # Checkpoint
TRAINING_DATA_PATH = os.path.join(SCRIPT_DIR, 'data', '1_bootstrap_training_data.csv')  # Dataset
LOG_FILE_PATH = os.path.join(SCRIPT_DIR, 'saved_models', 'training_log.txt')


# Ensure saved_models directory exists
os.makedirs(os.path.join(SCRIPT_DIR, 'saved_models'), exist_ok=True)

# ======================================================================================
# 🔹 Model Hyperparameters
# ======================================================================================
INPUT_DIM = 21
ENC_EMB_DIM = 256
DEC_EMB_DIM = 256
HID_DIM = 512
N_EPOCHS = 150
CLIP = 1
BATCH_SIZE = 16
VAL_SPLIT = 0.1
DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

# ======================================================================================
# 🔹 Load Vocabulary
# ======================================================================================
if not os.path.exists(VOCAB_PATH):
    raise FileNotFoundError(f"Vocabulary file not found at {VOCAB_PATH}")

with open(VOCAB_PATH, 'r') as f:
    vocab = json.load(f)

OUTPUT_DIM = len(vocab)

# ======================================================================================
# 🔹 Collate Function
# ======================================================================================
def collate_fn(batch):
    user_vectors, plan_sequences = zip(*batch)
    user_vectors = torch.stack(user_vectors)
    plan_sequences_padded = pad_sequence(list(plan_sequences), batch_first=False, padding_value=0)
    return user_vectors, plan_sequences_padded

# ======================================================================================
# 🔹 Evaluation Function
# ======================================================================================
def evaluate(model, val_loader, criterion):
    model.eval()
    val_loss = 0

    with torch.no_grad():
        for user_vectors, plan_sequences in val_loader:
            src = user_vectors.to(DEVICE).float()
            trg = plan_sequences.to(DEVICE)

            output = model(src, trg, 0)  # No teacher forcing
            output_dim = output.shape[-1]
            output = output[1:].reshape(-1, output_dim)
            trg = trg[1:].reshape(-1)

            loss = criterion(output, trg)
            val_loss += loss.item()

    return val_loss / len(val_loader)

# ======================================================================================
# 🔹 Training Function
# ======================================================================================
def train(resume_from_last=True):
    print(f"\n🚀 Training on: {DEVICE}")

    dataset = DietDataset(TRAINING_DATA_PATH)
    val_size = int(len(dataset) * VAL_SPLIT)
    train_size = len(dataset) - val_size
    train_dataset, val_dataset = random_split(dataset, [train_size, val_size])

    train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True, collate_fn=collate_fn)
    val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE, shuffle=False, collate_fn=collate_fn)

    encoder = Encoder(INPUT_DIM, ENC_EMB_DIM, HID_DIM)
    decoder = Decoder(OUTPUT_DIM, DEC_EMB_DIM, HID_DIM)
    model = Seq2Seq(encoder, decoder, DEVICE).to(DEVICE)

    optimizer = optim.Adam(model.parameters(), lr=1e-3)
    criterion = nn.CrossEntropyLoss(ignore_index=0)

    start_epoch = 0

    if resume_from_last and os.path.exists(MODEL_SAVE_PATH):
        print("🔁 Found saved model. Resuming training...")
        checkpoint = torch.load(MODEL_SAVE_PATH, map_location=DEVICE)
        model.load_state_dict(checkpoint['model_state_dict'])
        optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
        start_epoch = checkpoint['epoch'] + 1
    else:
        print("🆕 Starting new training...")

    # 🗂 Initialize Log File
    with open(LOG_FILE_PATH, 'w') as log_file:
        log_file.write(f"Epoch | Train Loss | Val Loss | Time (s)\n")
        log_file.write("-" * 40 + "\n")

    try:
        for epoch in range(start_epoch, N_EPOCHS):
            start_time = time.time()
            model.train()
            epoch_loss = 0

            for user_vectors, plan_sequences in train_loader:
                src = user_vectors.to(DEVICE).float()
                trg = plan_sequences.to(DEVICE)

                optimizer.zero_grad()
                output = model(src, trg)  # with teacher forcing

                output_dim = output.shape[-1]
                output = output[1:].reshape(-1, output_dim)
                trg = trg[1:].reshape(-1)

                loss = criterion(output, trg)
                loss.backward()

                torch.nn.utils.clip_grad_norm_(model.parameters(), CLIP)
                optimizer.step()

                epoch_loss += loss.item()

            avg_train_loss = epoch_loss / len(train_loader)
            val_loss = evaluate(model, val_loader, criterion)
            elapsed = time.time() - start_time

            # ✅ Print and log epoch info
            print(f"📊 Epoch: {epoch+1:02} | Train Loss: {avg_train_loss:.4f} | Val Loss: {val_loss:.4f} | Time: {elapsed:.2f}s")
            with open(LOG_FILE_PATH, 'a') as log_file:
                log_file.write(f"{epoch+1:02}    | {avg_train_loss:.4f}     | {val_loss:.4f}   | {elapsed:.2f}\n")

            # 💾 Save model (latest and versioned)
            torch.save({
                'epoch': epoch,
                'model_state_dict': model.state_dict(),
                'optimizer_state_dict': optimizer.state_dict(),
            }, MODEL_SAVE_PATH)

            versioned_path = MODEL_SAVE_PATH.replace(".pth", f"_epoch_{epoch+1:02}.pth")
            torch.save({
                'epoch': epoch,
                'model_state_dict': model.state_dict(),
                'optimizer_state_dict': optimizer.state_dict(),
            }, versioned_path)

    except Exception as e:
        print(f"\n💥 Training crashed: {e}")
        print(f"💾 Saving emergency backup to: {MODEL_SAVE_PATH}")
        torch.save({
            'epoch': epoch,
            'model_state_dict': model.state_dict(),
            'optimizer_state_dict': optimizer.state_dict(),
        }, MODEL_SAVE_PATH)

    print(f"\n✅ Training complete. Final model saved to: {MODEL_SAVE_PATH}")

# ======================================================================================
# 🔹 Entry Point
# ======================================================================================
if __name__ == '__main__':
    train()
