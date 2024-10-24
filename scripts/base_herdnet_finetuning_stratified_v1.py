# -*- coding: utf-8 -*-
"""Base_Herdnet_Finetuning_stratified_v1

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1h9HchpvlPruHShl2Oo4JGA1-O6-6d_3D

# DEMO - Training and testing HerdNet on nadir aerial images

## Installations
"""

# Check GPU
""" !nvidia-smi

# Install the dependencies
!pip install h5py
!pip install typing-extensions
!pip install wheel
!pip install albumentations>=1.0.3
!pip install fiftyone>=0.14.3
!pip install hydra-core>=1.1.0
!pip install opencv-python>=4.5.1.48
!pip install pandas>=1.2.3
!pip install pillow>=8.2.0
!pip install scikit-image>=0.18.1
!pip install scikit-learn>=1.0.2
!pip install scipy>=1.6.2
!pip install wandb>=0.10.33
!pip install numpy>=1.20.0 """

# Download and install the code
import sys


#!wandb login
import wandb
import random

"""## Create datasets"""

# Set the seed
from animaloc.utils.seed import set_seed

set_seed(9292)

#### Downloading and unziping the files
#zip file download (destination link)
# %cd /content/drive/MyDrive/
#!pip install --upgrade --no-cache-dir gdown
# Download the Train zip file

#!gdown https://drive.google.com/uc?id=1mI6Ve5v3sAj9h502g75GD1lZSYy4-FR4 -O /herdnet/DATASETS/Train_patches_stratified.zip
# Unzip the file to the specified directory
#!unzip -oq /herdnet/DATASETS/Train_patches_stratified.zip -d /herdnet/DATASETS/Train_patches_stratified

# Download the val zip file
#!gdown https://drive.google.com/uc?id=1-1lGSZVk-ts0TMo0n-sbwlBGKHhgh9O9 -O /herdnet/DATASETS/val_patches_stratified.zip
# Unzip the file to the specified directory
#!unzip -oq /herdnet/DATASETS/val_patches_stratified.zip -d /herdnet/DATASETS/val_patches_stratified

# Download the test zip file
#!gdown https://drive.google.com/uc?id=1-1r9sQlC-NxgcSvKKl0WPEmOpkzRV4KB -O /herdnet/DATASETS/test_patches_stratified.zip

# Unzip the file to the specified directory
#!unzip -oq /herdnet/DATASETS/test_patches_stratified.zip -d /herdnet/DATASETS/test_patches_stratified
# %%
# Commented out IPython magic to ensure Python compatibility.
# %matplotlib inline
# Showing some samples of patches and the annotations
import matplotlib.pyplot as plt
from animaloc.datasets import CSVDataset
from animaloc.data.batch_utils import show_batch, collate_fn
from torch.utils.data import DataLoader
import torch
import albumentations as A
batch_size = 8
NUM_WORKERS= 8
csv_path = '/herdnet/DATASETS/Train_patches_stratified/gt.csv'
image_path = '/herdnet/DATASETS/Train_patches_stratified'
dataset = CSVDataset(csv_path, image_path, [A.Normalize()])
dataloader = DataLoader(dataset, batch_size=batch_size, collate_fn=collate_fn, shuffle=True, num_workers= NUM_WORKERS)

sample_batch = next(iter(dataloader))
for i in range(len(sample_batch[1])):
  points = sample_batch[1][i]['points'].numpy()
  bbox= []
  for pt in points:
      bbox.append([pt[0]-2,pt[1]-2,pt[0]+2,pt[1]+2])
  print(len(sample_batch[1][i]['labels']))
  sample_batch[1][i]['annotations']=torch.tensor(bbox)
plt.figure(figsize=(16,2))
show_batch(sample_batch)
plt.savefig('/herdnet/show_patch.pdf')

# %%
# Training, validation and test datasets
import albumentations as A

from animaloc.datasets import CSVDataset
from animaloc.data.transforms import MultiTransformsWrapper, DownSample, PointsToMask, FIDT

patch_size = 512
num_classes = 2
down_ratio = 2

train_dataset = CSVDataset(
    csv_file = '/herdnet/DATASETS/Train_patches_stratified/gt.csv',
    root_dir = '/herdnet/DATASETS/Train_patches_stratified',
    albu_transforms = [
        A.VerticalFlip(p=0.5),
        A.HorizontalFlip(p=0.5),
        A.RandomRotate90(p=0.5),
        A.RandomBrightnessContrast(brightness_limit=0.2, contrast_limit=0.2, p=0.2),
        A.Blur(blur_limit=15, p=0.2),
        A.Normalize(p=1.0)
        ],
    end_transforms = [MultiTransformsWrapper([
        FIDT(num_classes=num_classes, down_ratio=down_ratio),
        PointsToMask(radius=2, num_classes=num_classes, squeeze=True, down_ratio=int(patch_size//16))
        ])]
    )

val_dataset = CSVDataset(
    csv_file = '/herdnet/DATASETS/val_patches_stratified/gt.csv',
    root_dir = '/herdnet/DATASETS/val_patches_stratified',
    albu_transforms = [A.Normalize(p=1.0)],
    end_transforms = [DownSample(down_ratio=down_ratio, anno_type='point')]
    )

test_dataset = CSVDataset(
    csv_file = '/herdnet/DATASETS/test_patches_stratified/gt.csv',
    root_dir = '/herdnet/DATASETS/test_patches_stratified',
    albu_transforms = [A.Normalize(p=1.0)],
    end_transforms = [DownSample(down_ratio=down_ratio, anno_type='point')]
    )

# Dataloaders
from torch.utils.data import DataLoader

train_dataloader = DataLoader(dataset = train_dataset, batch_size = 4, shuffle = True, num_workers= NUM_WORKERS)

val_dataloader = DataLoader(dataset = val_dataset, batch_size = 1, shuffle = False, num_workers= NUM_WORKERS)

test_dataloader = DataLoader(dataset = test_dataset, batch_size = 1, shuffle = False, num_workers= NUM_WORKERS)

"""## Define HerdNet for training"""

# Path to your .pth file (initial pth file)
import gdown
import torch
pth_path = None #'/herdnet/output/best_model.pth'
from pathlib import Path

dir_path = Path('/herdnet/output')  
dir_path.mkdir(parents=True, exist_ok=True)
pth_path= '/herdnet/DATASETS/20220413_herdnet_model.pth'
if not pth_path:
    gdown.download(
        'https://drive.google.com/uc?export=download&id=1-WUnBC4BJMVkNvRqalF_HzA1_pRkQTI_',
        '/herdnet/output/20220413_herdnet_model.pth'
        )
    pth_path = '/herdnet/output/20220413_herdnet_model.pth'

from animaloc.models import HerdNet
from torch import Tensor
from animaloc.models import LossWrapper
from animaloc.train.losses import FocalLoss
from torch.nn import CrossEntropyLoss
pretrained= False

herdnet = HerdNet(pretrained= False, num_classes=num_classes, down_ratio=down_ratio).cuda()
if not pretrained:
    pretrained_dict = torch.load(pth_path)['model_state_dict']
    #herdnet_dict = herdnet.state_dict()
    #pretrained_dict = {k: v for k, v in pretrained_dict.items() if k in herdnet_dict}
    #herdnet.load_state_dict(pretrained_dict, strict=False)

losses = [
    {'loss': FocalLoss(reduction='mean'), 'idx': 0, 'idy': 0, 'lambda': 1.0, 'name': 'focal_loss'},
    {'loss': CrossEntropyLoss(reduction='mean'), 'idx': 1, 'idy': 1, 'lambda': 1.0, 'name': 'ce_loss'}
    ]

herdnet = LossWrapper(herdnet, losses=losses)

#############Get model layers ###########################
def get_parameter_names(model): # getting the model layers
  param_dict= dict()
  for l, (name,param) in enumerate(model.named_parameters()):
    #print(l,":\t",name,type(param),param.requires_grad)
    param_dict[name]= l
  return param_dict
result = get_parameter_names(herdnet)
print(result)

"""# Freeze the alyers (different options)
1. half of a layer and other layers
"""

#Freeze half of a specified layer
def freeze_parts(model, get_parameter_names, layers_to_freeze, freeze_layer_half=None, lr=0.0001, unfreeze=False):
    params_to_update = []

    for l, (name, param) in enumerate(model.named_parameters()):
        res = any(ele in name for ele in layers_to_freeze)
        param.requires_grad = unfreeze if res else not unfreeze

        # Check if the current layer is the specified layer to freeze half of its parameters
        if freeze_layer_half is not None and freeze_layer_half in name:
            total_params = param.numel()
            half_params = total_params // 2
            param.requires_grad = unfreeze if l < half_params else not unfreeze

        if param.requires_grad:
            params_to_update.append({
                "params": param,
                "lr": lr,
            })

        # Print parameters to update
        if param.requires_grad:
            print(f"Trainable parameter: {name}")
        else:
            print(f"Frozen parameter: {name}")

    return params_to_update

#freezing half of one lyer+ other layers
params_to_update = freeze_parts(herdnet.model, get_parameter_names, layers_to_freeze=['base_layer','level0','level1','level2','level3'], freeze_layer_half='level_4', lr=0.0001, unfreeze=False)

"""# Freeze a complete layer"""

#Freeze the layers
def freeze_parts(model, get_parameter_names, layers_to_freeze, lr, unfreeze=False):
    params_to_update = []

    for l, (name, param) in enumerate(model.named_parameters()):
        res = any(ele in name for ele in layers_to_freeze)
        param.requires_grad = unfreeze if res else not unfreeze

        if param.requires_grad == True:
            params_to_update.append({
                "params": param,
                "lr": lr,
            })

        # Print parameters to update
        if param.requires_grad:
            print(f"Trainable parameter: {name}")
        else:
            print(f"Frozen parameter: {name}")

    return params_to_update

"""## Create the Trainer"""

from torch.optim import Adam
from animaloc.train import Trainer
from animaloc.eval import PointsMetrics, HerdNetStitcher, HerdNetEvaluator
from animaloc.utils.useful_funcs import mkdir

work_dir = '/herdnet/output'
mkdir(work_dir)

lr = 1e-4
weight_decay = 1e-3
epochs = 100

optimizer = Adam(params_to_update, lr=lr, weight_decay=weight_decay)

metrics = PointsMetrics(radius=20, num_classes=num_classes)

stitcher = HerdNetStitcher(
    model=herdnet,
    size=(patch_size,patch_size),
    overlap=160,
    down_ratio=down_ratio,
    reduction='mean'
    )

evaluator = HerdNetEvaluator(
    model=herdnet,
    dataloader=val_dataloader,
    metrics=metrics,
    stitcher= None, # stitcher,
    work_dir=work_dir,
    header='validation'
    )

trainer = Trainer(
    model=herdnet,
    train_dataloader=train_dataloader,
    optimizer=optimizer,
    num_epochs=epochs,
    evaluator=evaluator,
    # val_dataloader= val_dataloader      #loss evaluation
    work_dir=work_dir
    )

"""## Start training"""

import wandb
if wandb.run is not None:
  wandb.finish()
wandb.init(project="herdnet-finetuning")

trainer.start(warmup_iters=100, checkpoints='best', select='max', validate_on='f1_score', wandb_flag =True)

"""## Test the model"""

#save and load finetunned parameters
#herdnet = HerdNet()
#torch.save(herdnet.state_dict(), 'fine_tuned_base.pth')
#herdnet.load_state_dict(torch.load('fine_tuned_base.pth'))
pth_path = '/herdnet/output/fine_tuned_base.pth'
torch.save(herdnet.state_dict(), pth_path)

if 0:
    herdnet = HerdNet()
    herdnet.load_state_dict(torch.load(pth_path))
# Load trained parameters
if 0:
    from animaloc.models import load_model
    checkpoint = torch.load(pth_path, map_location=map_location)
    herdnet.load_state_dict(checkpoint['model_state_dict'])
    herdnet = load_model(herdnet, pth_path=pth_path)

# Create output folder
test_dir = '/herdnet/test_output'
mkdir(test_dir)

# Create an Evaluator
test_evaluator = HerdNetEvaluator(
    model=herdnet,
    dataloader=test_dataloader,
    metrics=metrics,
    stitcher=stitcher,
    work_dir=test_dir,
    header='test'
    )

# Start testing
test_f1_score = test_evaluator.evaluate(returns='f1_score')

# Print global F1 score (%)
print(f"F1 score = {test_f1_score * 100:0.0f}%")

# Get the detections
detections = test_evaluator.results
detections