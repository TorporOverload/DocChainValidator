from pypdf import PdfReader
import re
from typing import List, Optional, Dict, Any

def parse_pdf_to_pages_text(file_path: str) -> Optional[List[str]]:
    """
    parses a PDF file and extracts text from each page.
    returns a list of strings, where each string is the text of a page.
    """
    pages_text_content = []
    try:
        reader = PdfReader(file_path)
        num_pages = len(reader.pages)
        print(f"Number of pages in PDF: {num_pages}")
        print("Extracting text please wait...")
        for i, page in enumerate(reader.pages):
            # Display progress as a percentage
            print(f"Extracting text from PDF... {i + 1}/{num_pages} ({(i + 1) / num_pages * 100:.1f}%)", end='\r')
            
            text = page.extract_text()

            if text:
                text = re.sub(r'\s+', ' ', text).strip()
                pages_text_content.append(text)
            else:
                # Handle cases where a page might have no extractable text (e.g., image-only page)
                pages_text_content.append(f"[Page {i+1} - No text extracted or image-only page]")
        
        print("\nText extraction complete.") # Newline and clear rest of the line
            
    except FileNotFoundError:
        print(f"Error: PDF Document not found at {file_path}")
        return None
    except Exception as e:
        print(f"Error parsing PDF document '{file_path}': {e}")
        return None
    return pages_text_content


def get_pdf_title(file_path: str, doc_index: Dict[str, Any], validation: bool = False) -> Optional[str]:
    """
    Gets the title from the PDF file name.
    """
    try:
        # Extract filename from path
        if '/' in file_path:
            title = file_path.split('/')[-1]
        elif '\\' in file_path:
            title = file_path.split('\\')[-1]
        else:
            title = file_path

        # Check if title exists in doc_index
        if not validation and title in doc_index:
            print(f"Filename '{title}' already exists in the document index. Please use a different file name and try again.")
            return None
            
        return title

    except FileNotFoundError:
        print(f"Error: PDF Document not found at {file_path}")
        return None
    except Exception as e:
        print(f"Error extracting title from PDF document '{file_path}': {e}")
        return None

    
# if __name__ == "__main__":
#     # Example usage
#     path_to_pdf = "MSA_Vessel_Tracking___CPT245.pdf"
#     pages = parse_pdf_to_pages_text(path_to_pdf)
#     title = get_pdf_title(path_to_pdf)
#     print(f"Title of the PDF: {title}")
#     # for i, page in enumerate(pages):
#     #     print(f"Page {i+1}: {page[:100]}...")  # Print first 100 characters of each page