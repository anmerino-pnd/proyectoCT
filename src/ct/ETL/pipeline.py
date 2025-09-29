from ct.ETL.load import Load

def update_products():
    """
    Actualiza únicamente el vector store de productos.
    Extrae y transforma los productos y actualiza su vector store.
    """
    print("\n--- Actualizando productos ---")
    load = Load()
    products_docs = load.load_products()
    if products_docs:
        load.products_vs(products_docs)
        print("✅ Vector store de productos actualizado correctamente.")
    else:
        print("No se pudo actualizar el vector store de productos.")


def update_sales():
    """
    Actualiza únicamente el vector store de ventas (ofertas).
    Carga primero el vector store de productos (si es necesario)
    y actualiza solo las ofertas.
    """
    print("\n--- Actualizando ventas (ofertas) ---")
    load = Load()
    sales_docs = load.load_sales()
    if sales_docs:
        load.sales_products_vs(sales_docs)
        print("✅ Vector store de ventas (ofertas) actualizado correctamente.")
    else:
        print("No se pudo actualizar el vector store de ventas.")


def update_all():
    """
    Actualiza ambos vector stores (productos y ventas).
    ⚠️ Nota: esta función puede tardar más tiempo porque procesa todo el pipeline completo.
    """
    print("\n=== Actualizando productos y ventas (pipeline completo) ===")
    load = Load()

    # Productos
    print("\n--- Procesando productos ---")
    products_docs = load.load_products()
    if not products_docs:
        print("El pipeline de productos no se pudo completar. Saliendo.")
        return
    load.products_vs(products_docs)

    # Ventas
    print("\n--- Procesando ventas (ofertas) ---")
    sales_docs = load.load_sales()
    if not sales_docs:
        print("El pipeline de ventas no se pudo completar. Saliendo.")
        return
    load.sales_products_vs(sales_docs)

    print("\n✅ Pipeline completo (productos y ventas) actualizado exitosamente.")

