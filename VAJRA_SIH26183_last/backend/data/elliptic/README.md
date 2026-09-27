Place the 3 Elliptic dataset CSVs here (not committed to the repo --
too large, and redistribution isn't clearly covered by Kaggle's
license):

    elliptic_txs_features.csv
    elliptic_txs_classes.csv
    elliptic_txs_edgelist.csv

Download: https://www.kaggle.com/datasets/ellipticco/elliptic-data-set
(free, requires accepting the dataset's license on Kaggle)

Then from backend/:
    python3 engine/train_elliptic_benchmark.py
