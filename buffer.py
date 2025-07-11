import os
import numpy as np
import torch
from typing import Any, Dict, Tuple, Generator, List, Optional, Union
from dataclasses import dataclass
from torchtyping import TensorType
from torch.utils.data import Sampler
from torch.utils.data import DataLoader, Dataset
from torch.nn.utils.rnn import pad_sequence

@dataclass
class PPORLElement:
    """
    Data class to store elements for PPO RL.

    Attributes:
        input_ids (torch.Tensor): The query tensor, i.e., the prompt tokens. Should be a long tensor.
        actions (torch.Tensor): The response tensor, i.e., the output tokens. Should be a long tensor.
        logprobs (torch.Tensor): The log probabilities over the response tokens generated by the policy network
                                 (i.e., the autoregressive model). Should be a float tensor of the same size as tokens.
        values (torch.Tensor): The values for each token generated from the value network or value head.
                               Should be a float tensor of the same size as tokens.
        rewards (torch.Tensor): The rewards for each token outputted in response.
                                Should be a float tensor of the same size as tokens.
    """

    input_ids: TensorType["input_ids"]
    actions: TensorType["action_size"]
    logprobs: TensorType["action_size"]
    values: TensorType["action_size"]
    rewards: TensorType["action_size"]

@dataclass
class PPORLVisionElement(PPORLElement):
    """
    Data class to store elements for PPO RL

    Attributes:
        image_ids (torch.Tensor): The vision query tensor i.e. the prompt tokens. Should be a long tensor.
    """
    image_ids: TensorType["image_ids"]



class PPORLBatchSampler(Sampler):
    def __init__(self, data_source, batch_size):
        self.data_source = data_source
        self.batch_size = batch_size

    def __iter__(self):
        batch = []
        for idx in range(len(self.data_source)):
            batch.append(idx)
            if len(batch) == self.batch_size:
                yield batch
                batch = []
        if batch:
            # If the last batch is smaller than the desired batch size, fill it from the start of the datasetneeded = self.batch_size - len(batch)
            needed = self.batch_size - len(batch)
            while needed > 0:
                for i in range(min(needed, len(self.data_source))):
                    batch.append(i)  # Append from the start
                needed = self.batch_size - len(batch)
            yield batch

    def __len__(self):
        return (len(self.data_source) + self.batch_size - 1) // self.batch_size


class PPORLVisionDataset(Dataset):
    def __init__(self, ppo_rl_elements):
        self.ppo_rl_elements = ppo_rl_elements

    def __len__(self):
        return len(self.ppo_rl_elements)

    def __getitem__(self, idx):
        return self.ppo_rl_elements[idx]


def ppo_rl_collate_fn(batch, pad_token_id):
    # Initialize containers for batched data
    input_ids = []
    actions = []
    logprobs = []
    values = []
    rewards = []
    image_ids = []  # For PPORLVisionElement

    # Check if any element in the batch has 'image_ids' to determine if it's a mixed or vision-only batch
    has_image_ids = any(hasattr(element, 'image_ids') for element in batch)

    for element in batch:
        input_ids.append(element.input_ids)
        actions.append(element.actions)
        logprobs.append(element.logprobs)
        values.append(element.values)
        rewards.append(element.rewards)
        
        if has_image_ids:
            # If 'image_ids' attribute exists, append it, otherwise append a placeholder (e.g., None or zeros)
            if hasattr(element, 'image_ids'):
                image_ids.append(element.image_ids)
            else:
                # Assuming you have a way to generate a placeholder or decide to skip
                image_ids.append(None)  # Adjust this based on how you wish to handle non-vision elements

    # Compile everything into a dictionary, conditionally include 'image_ids'
    batched_data = {
        "input_ids": pad_sequence(input_ids, batch_first=True, padding_value=pad_token_id),
        "actions": pad_sequence(actions, batch_first=True, padding_value=pad_token_id),
        "logprobs": pad_sequence(logprobs, batch_first=True, padding_value=0.0),
        "values": pad_sequence(values, batch_first=True, padding_value=0.0),
        "rewards": pad_sequence(rewards, batch_first=True, padding_value=0.0),
    }
    
    if has_image_ids:
        # Handle cases where there are missing 'image_ids' if necessary
        batched_data["image_ids"] = pad_sequence(image_ids, batch_first=True, padding_value=0)

    return batched_data