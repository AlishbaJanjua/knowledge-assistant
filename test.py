from loaders.pdf_loader import load_documents

chunks = load_documents()

print("Number of chunks:", len(chunks))

for chunk in chunks[:2]:
    print(chunk.page_content[:500])