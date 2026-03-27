import pandas as pd
import json
import os

def update_stock_names():
    url = "https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq0000001vg2-att/data_j.xls"
    mapping_path = os.path.join(os.path.dirname(__file__), "stock_names.json")
    
    print("Downloading JPX data from:", url)
    try:
        # Pandasは引数URLから直接Excelを読み込める
        df = pd.read_excel(url)
        
        # 必要なデータを抽出 (データ行は通常2行目以降から。ヘッダーの列名を確認)
        # 実際のカラム名が「コード」「銘柄名」であることを期待
        
        stock_dict = {}
        # xlsのフォーマットにより、実際の銘柄行を取り出す
        target_columns = ["コード", "銘柄名"]
        
        for index, row in df.iterrows():
            if "コード" in row and "銘柄名" in row:
                code_raw = str(row["コード"]).strip()
                name_raw = str(row["銘柄名"]).strip()
                
                # '1234'のように末尾が数字4桁のもの（一部5桁もあり得るが、東証コードは基本的に数値）
                if code_raw.isdigit() and len(code_raw) >= 4:
                    stock_dict[code_raw] = name_raw

        # 既存ファイルの読み込み
        if os.path.exists(mapping_path):
            with open(mapping_path, "r", encoding="utf-8") as f:
                existing_dict = json.load(f)
        else:
            existing_dict = {}

        # 統合
        before_count = len(existing_dict)
        existing_dict.update(stock_dict)
        after_count = len(existing_dict)
        
        # 保存
        with open(mapping_path, "w", encoding="utf-8") as f:
            json.dump(existing_dict, f, ensure_ascii=False, indent=2)

        print(f"Successfully updated stock_names.json!")
        print(f"Before: {before_count} stocks. After: {after_count} stocks.")
        print(f"Added new: {after_count - before_count} stocks.")

    except ImportError as ie:
        print("Missing required library (xlrd or openpyxl):", ie)
        print("Please install them using: pip install xlrd openpyxl")
    except Exception as e:
        print("Error reading JPX data:", e)

if __name__ == "__main__":
    update_stock_names()
