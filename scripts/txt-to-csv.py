import os
import csv

def txt_to_csv(input_file, output_file, replace_characters=None):
    """
    Converts a .txt file to a .csv file, replacing specified characters.

    Args:
        input_file (str): Path to the input .txt file.
        output_file (str): Path to the output .csv file.
        replace_characters (dict): Dictionary of characters to replace (key: old, value: new).
    """
    if replace_characters is None:
        replace_characters = {
            'à': 'CLOSED',
            ' ': ','
        }

    try:
        with open(input_file, 'r', encoding='utf-8') as txt_file, open(output_file, 'w', newline='', encoding='utf-8') as csv_file:
            csv_writer = csv.writer(csv_file)
            
            for line in txt_file:
                # Reverse the line if the input filename contains "east"
                if "east" in os.path.basename(input_file).lower():
                    line = ' '.join(reversed(line.split()))
                
                # Replace specified characters
                for old_char, new_char in replace_characters.items():
                    line = line.replace(old_char, new_char)
                
                # Replace "12:" with "00:" for times ending with "A"
                line = ' '.join(
                    time.replace("12:", "00:") if time.startswith("12:") and "A" in time else time
                    for time in line.split()
                )
                
                # Split the line into columns and write to CSV
                csv_writer.writerow(line.split(','))
        
        print(f"Conversion successful! CSV saved at: {output_file}")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    # Define input and output directories
    input_dir = os.path.join("", "4_3_2025", "txt")
    output_dir = os.path.join("", "4_3_2025", "csv")

    # Ensure the output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Loop through all .txt files in the input directory
    for filename in os.listdir(input_dir):
        if filename.endswith(".txt"):
            input_txt = os.path.join(input_dir, filename)
            output_csv = os.path.join(output_dir, filename.replace(".txt", ".csv"))

            # Convert the file
            txt_to_csv(input_txt, output_csv)
