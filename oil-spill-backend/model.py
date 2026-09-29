import os
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
import torchvision.transforms as transforms
import torchvision.datasets as datasets
import torchvision.models as models

def train_classifier():
    # Absolute paths provided for your dataset
    data_dir = r"C:\Tevin Projects\Code Projects\SIH\data"
    
    # 1. Define Transforms (Resize and scale pixels to [0.0, 1.0])
    transform = transforms.Compose([
        transforms.Resize((224, 224)),  # Standard size for ResNet
        transforms.Grayscale(num_output_channels=3), # ResNet expects 3 channels (we duplicate grayscale)
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])

    # 2. Automatically load Class_0 and Class_1 using ImageFolder
    # ImageFolder automatically assigns label 0 to Class_0 and label 1 to Class_1
    dataset = datasets.ImageFolder(root=data_dir, transform=transform)
    
    dataloader = DataLoader(dataset, batch_size=8, shuffle=True)
    print(f"Found {len(dataset)} total images across classes: {dataset.classes}")

    # Device configuration (GPU if available)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    # 3. Initialize a Pre-trained ResNet18 Classifier for 2 classes (Class 0 vs Class 1)
    model = models.resnet18(weights=models.ResNet18_Weights.DEFAULT)
    
    # Modify the final fully connected layer to output 2 classes
    num_ftrs = model.fc.in_features
    model.fc = nn.Linear(num_ftrs, 2)
    model = model.to(device)

    # Loss function and Optimizer
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.0001)

    # 4. Training Loop
    num_epochs = 10
    for epoch in range(num_epochs):
        model.train()
        epoch_loss = 0
        correct_preds = 0
        total_preds = 0

        for images, labels in dataloader:
            images = images.to(device)
            labels = labels.to(device)

            # Forward pass
            outputs = model(images)
            loss = criterion(outputs, labels)

            # Backward pass & optimization
            optimizer.zero_init() if hasattr(optimizer, 'zero_init') else optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            epoch_loss += loss.item()
            
            # Calculate accuracy
            _, predicted = torch.max(outputs.data, 1)
            total_preds += labels.size(0)
            correct_preds += (predicted == labels).sum().item()

        epoch_acc = 100 * correct_preds / total_preds
        print(f"Epoch [{epoch+1}/{num_epochs}] | Loss: {epoch_loss/len(dataloader):.4f} | Accuracy: {epoch_acc:.2f}%")

    # Save trained model weights
    torch.save(model.state_dict(), "oil_spill_classifier.pth")
    print("Training complete! Model saved as oil_spill_classifier.pth")

if __name__ == "__main__":
    train_classifier()