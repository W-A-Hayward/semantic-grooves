# Automatically download the Kaggle dataset
import kagglehub

path = kagglehub.dataset_download("nolanbconaway/pitchfork-data", output_dir="./db")

print(path)