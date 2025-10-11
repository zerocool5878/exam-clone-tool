# Create a simple test sheet icon using Python
from PIL import Image, ImageDraw
import os

def create_test_icon():
    # Create a 32x32 icon (standard size)
    size = 32
    img = Image.new('RGBA', (size, size), (255, 255, 255, 0))  # Transparent background
    draw = ImageDraw.Draw(img)
    
    # Draw paper outline (white with border)
    paper_rect = [4, 2, 28, 30]
    draw.rectangle(paper_rect, fill=(255, 255, 255, 255), outline=(0, 0, 0, 255), width=1)
    
    # Draw horizontal lines (like a test sheet)
    for y in range(8, 26, 3):
        draw.line([(6, y), (26, y)], fill=(200, 200, 200, 255), width=1)
    
    # Draw some "question circles" (A B C D bubbles)
    bubble_positions = [(8, 9), (12, 9), (16, 9), (20, 9)]  # First row
    for x, y in bubble_positions:
        draw.ellipse([x, y, x+2, y+2], outline=(100, 100, 100, 255), width=1)
    
    # Fill one bubble (selected answer)
    draw.ellipse([12, 9, 14, 11], fill=(0, 100, 200, 255))
    
    # Second row of bubbles
    bubble_positions2 = [(8, 15), (12, 15), (16, 15), (20, 15)]
    for x, y in bubble_positions2:
        draw.ellipse([x, y, x+2, y+2], outline=(100, 100, 100, 255), width=1)
    
    # Fill another bubble
    draw.ellipse([16, 15, 18, 17], fill=(0, 100, 200, 255))
    
    # Save as ICO file
    img.save('c:\\Users\\zeroc\\OneDrive\\Documents\\test_icon.ico', format='ICO')
    print("Test sheet icon created: test_icon.ico")

if __name__ == "__main__":
    try:
        create_test_icon()
    except ImportError:
        print("PIL not available - will use default icon")
    except Exception as e:
        print(f"Could not create icon: {e}")