# 🔽 Importing Required Libraries
import pandas as pd                  # For reading and manipulating CSV/tabular data
import torch                         # Core PyTorch library (tensor operations)
from torch.utils.data import Dataset # Base class for custom datasets in PyTorch
import json                          # For parsing stringified JSON (like "[1, 2, 3]")

# ------------------------------------------------------------------------------
# ✅ Utility Function: Check if a string is a valid JSON list (not just valid JSON)
# This is used to safely parse user_vector and plan_sequence columns from CSV
# ------------------------------------------------------------------------------

def is_valid_json(s):
    """
    Returns True if the input string is a valid JSON list (e.g., "[1, 2, 3]"),
    False if it’s invalid JSON or any JSON structure that's not a list (like a dict).
    """
    try:
        return isinstance(json.loads(s), list)
    except:
        return False  # Invalid JSON or not a list

# ------------------------------------------------------------------------------
# ✅ Custom Dataset Class: DietDataset
# Loads a CSV file where each row represents a user profile + diet plan
# Used for training a sequence generation model (encoder-decoder)
# ------------------------------------------------------------------------------

class DietDataset(Dataset):
    def __init__(self, csv_path):
        """
        Initialize the dataset from a CSV file.
        Required columns: 'user_vector' (str list) and 'plan_sequence' (str list).
        """

        # 🔹 Step 1: Load CSV data using pandas
        df = pd.read_csv(csv_path)

        # 🔹 Step 2: Drop rows with missing (NaN) values in key columns
        df = df.dropna(subset=['user_vector', 'plan_sequence'])

        # 🔹 Step 3: Keep only rows where 'user_vector' is a valid JSON list
        df = df[df['user_vector'].apply(is_valid_json)]

        # 🔹 Step 4: Also ensure 'plan_sequence' is a valid JSON list
        df = df[df['plan_sequence'].apply(is_valid_json)]

        # 🔹 Step 5: Convert 'user_vector' stringified JSON → Python list
        # e.g., "[0.1, 0.3]" → [0.1, 0.3]
        df['user_vector'] = df['user_vector'].apply(json.loads)

        # 🔹 Step 6: Convert 'plan_sequence' stringified JSON → list of integers
        # e.g., "[5, 22, 101]" → [5, 22, 101]
        df['plan_sequence'] = df['plan_sequence'].apply(json.loads)

        # 🔹 Step 7: Convert list of user vectors to a float tensor
        # Shape: [num_samples, vector_dim]
        self.user_vectors = torch.tensor(df['user_vector'].tolist(), dtype=torch.float32)

        # 🔹 Step 8: Define start-of-sequence and end-of-sequence tokens
        # These help the model understand sequence boundaries during training
        sos_token = 1  # <sos>
        eos_token = 2  # <eos>

        # 🔹 Step 9: Prepare plan sequences with <sos> and <eos> tokens added
        # For each plan: [45, 76] → [1, 45, 76, 2]
        # This helps the decoder learn when to start and stop generating
        self.plan_sequences = [
            torch.tensor([sos_token] + seq + [eos_token], dtype=torch.long)
            for seq in df['plan_sequence']
        ]

    def __len__(self):
        """
        Returns the number of samples in the dataset.
        Needed by PyTorch to know how many batches to run.
        """
        return len(self.user_vectors)

    def __getitem__(self, idx):
        """
        Fetch one data sample (user_vector, plan_sequence) pair by index.
        Used when iterating over dataset during training.
        """
        return self.user_vectors[idx], self.plan_sequences[idx]
