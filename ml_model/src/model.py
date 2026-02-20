# =====================================================================================
# model.py — PyTorch Seq2Seq Model for AI Diet Planning
# =====================================================================================

import torch                    # Core PyTorch functionality
import torch.nn as nn           # Neural network layers (Linear, LSTM, etc.)
import random                   # For teacher forcing strategy in training

# =====================================================================================
# 🔹 ENCODER: Converts user profile vector into a hidden state for the decoder
# =====================================================================================
class Encoder(nn.Module):
    def __init__(self, input_dim, emb_dim, hid_dim):
        """
        input_dim: Number of features in the user vector (e.g., age, BMI, lab values)
        emb_dim: Embedding dimension (projects input to higher dimension)
        hid_dim: Hidden size of LSTM
        """
        super().__init__()
        self.hid_dim = hid_dim
        self.embedding = nn.Linear(input_dim, emb_dim)
        self.rnn = nn.LSTM(emb_dim, hid_dim)
        self.dropout = nn.Dropout(0.5)
        
    def forward(self, src):
        """
        src: [batch_size, input_dim]
        Returns: hidden, cell → [1, batch_size, hid_dim]
        """
        embedded = self.dropout(torch.relu(self.embedding(src)))
        embedded = embedded.unsqueeze(0)
        outputs, (hidden, cell) = self.rnn(embedded)
        return hidden, cell

# =====================================================================================
# 🔹 DECODER: Predicts the food sequence token-by-token using encoder’s hidden state
# =====================================================================================
class Decoder(nn.Module):
    def __init__(self, output_dim, emb_dim, hid_dim):
        """
        output_dim: Size of the food vocabulary (total number of unique food IDs)
        emb_dim: Embedding size for token IDs
        hid_dim: Hidden size for decoder LSTM
        """
        super().__init__()
        self.output_dim = output_dim
        self.embedding = nn.Embedding(output_dim, emb_dim)
        self.rnn = nn.LSTM(emb_dim, hid_dim)
        self.fc_out = nn.Linear(hid_dim, output_dim)
        self.dropout = nn.Dropout(0.5)
        
    def forward(self, input, hidden, cell):
        """
        input: [batch_size] → current token (food ID)
        hidden, cell: from previous step or encoder
        """
        input = input.unsqueeze(0)
        embedded = self.dropout(self.embedding(input))
        output, (hidden, cell) = self.rnn(embedded, (hidden, cell))
        prediction = self.fc_out(output.squeeze(0))
        return prediction, hidden, cell

# =====================================================================================
# 🔹 SEQ2SEQ WRAPPER: Combines Encoder & Decoder for training and generation
# =====================================================================================
class Seq2Seq(nn.Module):
    def __init__(self, encoder, decoder, device):
        """
        encoder: instance of Encoder
        decoder: instance of Decoder
        device: torch.device ('cuda' or 'cpu')
        """
        super().__init__()
        self.encoder = encoder
        self.decoder = decoder
        self.device = device
        
    def forward(self, src, trg, teacher_forcing_ratio=0.5):
        """
        TRAINING METHOD: Used during model training with teacher forcing.
        src: [batch_size, input_dim]      → user vector
        trg: [trg_len, batch_size]        → target food ID sequence
        """
        batch_size = src.shape[0]
        trg_len = trg.shape[0]
        trg_vocab_size = self.decoder.output_dim
        outputs = torch.zeros(trg_len, batch_size, trg_vocab_size).to(self.device)
        hidden, cell = self.encoder(src)
        input = trg[0, :]
        for t in range(1, trg_len):
            output, hidden, cell = self.decoder(input, hidden, cell)
            outputs[t] = output
            teacher_force = random.random() < teacher_forcing_ratio
            top1 = output.argmax(1)
            input = trg[t] if teacher_force else top1
        return outputs

    # =====================================================================================
    # 🔹 NEW GENERATION METHOD: Used for inference to create a diet plan
    # =====================================================================================
    @torch.no_grad()  # Disable gradient calculation for efficiency
    def generate(self, src_tensor, meal_names, top_k=5, allowed_ids=None):
        """
        INFERENCE METHOD: Generates a sequence of food items for a user.
        
        Args:
            src_tensor (torch.Tensor): The user's feature vector [1, input_dim].
            meal_names (list): A list of meal names, used to determine sequence length.
            top_k (int): The number of top choices to sample from at each step.
            allowed_ids (list): A list of integer IDs for foods that are allowed.
        
        Returns:
            list: A list of generated food IDs.
        """
        self.eval()  # Set the model to evaluation mode (disables dropout, etc.)

        max_len = len(meal_names)
        batch_size = src_tensor.shape[0] # Should be 1 for single-user generation
        
        # Get the initial context from the user's data
        hidden, cell = self.encoder(src_tensor)
        
        # Start with a <sos> token. Assuming 0 is your <sos> token ID.
        # If your vocab is different, change this to your actual <sos> ID.
        input_token = torch.tensor([0], device=self.device) 
        
        # Store the generated food IDs
        generated_ids = []

        for _ in range(max_len):
            # Decode one step
            prediction, hidden, cell = self.decoder(input_token, hidden, cell)
            # prediction shape: [1, output_dim]

            # --- Apply Allowed Foods Mask ---
            if allowed_ids is not None:
                # Create a mask filled with a large negative number
                mask = torch.full_like(prediction, -float('inf'))
                # For the allowed indices, copy the original logit values
                mask[:, allowed_ids] = prediction[:, allowed_ids]
                # The final prediction is the masked prediction
                prediction = mask

            # --- Top-K Sampling ---
            # 1. Get the top K logits and their indices
            top_k_logits, top_k_indices = torch.topk(prediction, k=top_k, dim=1)
            
            # 2. Convert these K logits into probabilities using softmax
            top_k_probs = torch.softmax(top_k_logits, dim=1)
            
            # 3. Sample from this new, smaller probability distribution
            sampled_relative_index = torch.multinomial(top_k_probs, num_samples=1)
            
            # 4. Map the sampled index back to the original vocabulary index
            next_token = torch.gather(top_k_indices, 1, sampled_relative_index).squeeze(1)
            
            # Add the generated food ID to our list
            generated_ids.append(next_token.item())
            
            # The next input to the decoder is the token we just generated
            input_token = next_token
        
        return generated_ids