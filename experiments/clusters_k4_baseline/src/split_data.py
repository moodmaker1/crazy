# src/split_data.py
from sklearn.model_selection import train_test_split

def split_dataset(df_or_X, y=None, test_size=0.2, val_size=0.1, random_state=42):
    """
    - 지도학습: y가 주어지면 X/y를 함께 분리
    - 비지도학습(군집): y=None이면 X만 분리하고 y_*는 None으로 반환
    """
    X = df_or_X

    # 비지도 (군집) — y가 없을 때
    if y is None:
        X_train, X_temp = train_test_split(
            X, test_size=test_size, random_state=random_state, shuffle=True
        )
        val_ratio = val_size / (1 - test_size)
        X_val, X_test = train_test_split(
            X_temp, test_size=val_ratio, random_state=random_state, shuffle=True
        )
        y_train = y_val = y_test = None
        return X_train, X_val, X_test, y_train, y_val, y_test

    # 지도학습 — y가 있을 때
    X_train, X_temp, y_train, y_temp = train_test_split(
        X, y, test_size=test_size, random_state=random_state, shuffle=True
    )
    val_ratio = val_size / (1 - test_size)
    X_val, X_test, y_val, y_test = train_test_split(
        X_temp, y_temp, test_size=val_ratio, random_state=random_state, shuffle=True
    )
    return X_train, X_val, X_test, y_train, y_val, y_test
