import pandas as pd;
import numpy as np;
import torch
from transformers import AdamW, get_scheduler
from collections import defaultdict
import warnings

import engine
from model import BertFGBC, RobertaFGBC, XLNetFGBC
from dataset import DatasetBert, DatasetRoberta, DatasetXLNet
from utils import train_validate_test_split
from common import get_parser
from evaluate import test_evaluate

parser = get_parser()
args = parser.parse_args()
warnings.filterwarnings("ignore")
np.random.seed(args.seed)
torch.manual_seed(args.seed)
torch.cuda.manual_seed(args.seed)

def run():
    df = pd.read_csv(args.dataset_file).dropna()
    print(set(df.label.values))
    
    train_df, valid_df, test_df = train_validate_test_split(df)

    print("train len - {}, valid len - {}, test len - {}".format(len(train_df), len(valid_df),len(test_df)))

    train_dataset = generate_dataset(train_df)
    train_data_loader = torch.utils.data.DataLoader(
        dataset = train_dataset,
        batch_size = args.train_batch_size,
        shuffle = True
    )

    valid_dataset = generate_dataset(valid_df)
    valid_data_loader = torch.utils.data.DataLoader(
        dataset = valid_dataset,
        batch_size = args.valid_batch_size,
        shuffle = True
    )

    test_dataset = generate_dataset(test_df)
    test_data_loader = torch.utils.data.DataLoader(
        dataset = test_dataset,
        batch_size = args.test_batch_size,
        shuffle = False
    )
    
    device = set_device()

    model = set_model()
    model = model.to(device)

    num_train_steps = int(len(train_df) / args.train_batch_size * args.epochs)
    
    optimizer = AdamW(
        params = model.parameters(),
        lr = args.learning_rate,
        weight_decay = args.weight_decay,
        eps = args.adamw_epsilon
    )

    scheduler = get_scheduler(
        "linear",
        optimizer = optimizer,
        num_warmup_steps = args.warmup_steps,
        num_training_steps = num_train_steps
    )

    print("---Starting Training---")

    history = defaultdict(list)
    best_acc = 0.0
    
    for epoch in range(args.epochs):
        print(f'Epoch {epoch + 1}/{args.epochs}')
        print('-'*10)

        train_acc, train_loss = engine.train_fn(train_data_loader, model, optimizer, device, scheduler)
        print(f'Epoch {epoch + 1} --- Training loss: {train_loss} Training accuracy: {train_acc}')
        val_acc, val_loss = engine.eval_fn(valid_data_loader, model, device)
        print(f'Epoch {epoch + 1} --- Validation loss: {val_loss} Validation accuracy: {val_acc}')
        history['train_acc'].append(train_acc)
        history['train_loss'].append(train_loss)
        history['val_acc'].append(val_acc)
        history['val_loss'].append(val_loss)

        if val_acc>best_acc:
            torch.save(model.state_dict(), f"{args.model_path}{args.pretrained_model}---val_acc---{val_acc}.bin")

    print(f'\n---History---\n{history}')
    print("##################################### Testing ############################################")
    test_evaluate(test_df, test_data_loader, model, device)  
      
    del model, train_data_loader, valid_data_loader, train_dataset, valid_dataset
    torch.cuda.empty_cache()
    torch.cuda.synchronize()
    print("##################################### Task End ############################################")

def generate_dataset(df):
    if(args.pretrained_model == "bert-base-uncased"):
        return DatasetBert(text=df.text.values, target=df.target.values)
    elif(args.pretrained_model== "roberta-base"):
        return DatasetRoberta(text=df.text.values, target=df.target.values)
    elif(args.pretrained_model== "xlnet-base-cased"):
        return DatasetXLNet(text=df.text.values, target=df.target.values)

def set_model():
    if(args.pretrained_model == "bert-base-uncased"):
        return BertFGBC()
    elif(args.pretrained_model == "roberta-base"):
        return RobertaFGBC()
    elif(args.pretrained_model == "xlnet-base-cased"):
        return XLNetFGBC()

def set_device():
    device = ""
    if(args.device=="cpu"):
        device = "cpu"
    else:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        if(device=="cpu"):
            print("GPU not available.")
    return device


if __name__=="__main__":
    run()