from ct.ETL.load import Load

def run_etl_pipeline():
    """
    Función principal para ejecutar todo el pipeline de ETL.
    Extrae, transforma y carga los datos de productos y ventas, creando los vector stores correspondientes.
    """
    print("Iniciando el pipeline ETL...")

    # Instanciar la clase Load
    load = Load()

    # 1. Cargar y transformar productos
    print("\n--- Procesando productos ---")
    products_docs = load.load_products()
    if products_docs:
        # 2. Crear el vector store de productos
        load.products_vs(products_docs)
    else:
        print("El pipeline de productos no se pudo completar. Saliendo.")
        return

    # 3. Cargar y transformar ventas (ofertas)
    print("\n--- Procesando ventas (ofertas) ---")
    sales_docs = load.load_sales()
    if sales_docs:
        # 4. Crear el vector store de ventas, usando el de productos como base
        load.sales_products_vs(sales_docs)
    else:
        print("El pipeline de ventas no se pudo completar. Saliendo.")
        return

    print("\n✅ Pipeline ETL completado exitosamente.")

if __name__ == "__main__":
    run_etl_pipeline()

