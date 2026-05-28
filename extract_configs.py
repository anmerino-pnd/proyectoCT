import re
import os

source_dir = 'C:/Users/angel.merino/Documents/proyectoCT/quarto'
output_dir = 'C:/Users/angel.merino/Documents/proyectoCT/quarto/configs'

# Pattern to match markdown headers (works with UTF-8)
header_pattern = re.compile(r'^(#{1,6})\s+(.+?)(?:\s*$|\s*$)', re.MULTILINE | re.IGNORECASE)

# Process each .qmd file
for filename in sorted(os.listdir(source_dir)):
    if filename.endswith('.qmd'):
        filepath = os.path.join(source_dir, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract YAML header
        yaml_pattern = re.compile(r'---\s*\n(.*?)\n---', re.DOTALL)
        yaml_match = yaml_pattern.search(content)
        yaml_content = yaml_match.group(1) if yaml_match else ''
        
        # Extract titles and subtitles
        headers = header_pattern.findall(content)
        titles = []
        for match in headers:
            level = len(match[0])
            text = match[1].strip()
            titles.append(f'[{level}]{text}')
        
        # Create output file
        output_path = os.path.join(output_dir, f'{filename.replace(".qmd", ".yaml")}')
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f'# Archivo: {filename}\n')
            f.write(f'# Títulos y subtítulos:\n')
            for title in titles:
                f.write(f'- {title}\n')
            f.write(f'\n---\n')
            f.write(f'YAML Header:\n')
            f.write(f'---\n{yaml_content}---\n')
        
        print(f'Procesado: {filename} ({len(titles)} títulos)')

print('\n¡Procesado completo!')
