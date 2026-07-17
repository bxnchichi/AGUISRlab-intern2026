
import json
import pandas as pd

# 1. Create your DataFrame and Dictionary
df1 = pd.DataFrame({'Name': ['Alice', 'Bob'], 'Age': [25, 30]})
df2 = pd.DataFrame({'City': ['Tokyo', 'Osaka'], 'Rank': [1, 2]})

my_dict = {
    'group_1': df1, 
    'group_2': df2
}

# 2. Convert DataFrames to dictionaries so JSON can understand them
dict_for_json = {key: value.to_dict(orient='records') for key, value in my_dict.items()}

# 3. Save to a JSON file
with open('Data/data.json', 'w') as f:
    json.dump(dict_for_json, f, indent=4)
