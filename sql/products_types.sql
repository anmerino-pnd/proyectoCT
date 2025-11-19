SELECT 
    pro.tipo, 
    COUNT(DISTINCT pro.idProductos) AS cantidad_productos_unicos
FROM productos pro
JOIN existencias e 
    ON pro.idProductos = e.idProductos
JOIN precio pre 
    ON pro.idProductos = pre.idProducto
JOIN categorias cat 
    ON pro.idCategoria = cat.idCategoria
WHERE pro.idProductos > 0
    AND pro.activo = 1
    
GROUP BY pro.tipo 
ORDER BY cantidad_productos_unicos DESC;


SELECT 
	cat.idCategoria,
	cat.nombre,
	pro.tipo
FROM productos pro
JOIN existencias e 
	ON pro.idProductos = e.idProductos
JOIN precio pre 
	ON pro.idProductos = pre.idProducto
JOIN categorias cat 
	ON pro.idCategoria = cat.idCategoria
WHERE pro.activo = 1
	AND pro.tipo IS NOT NULL
	AND pro.tipo != ''
GROUP BY pro.tipo
ORDER BY pro.tipo;

SELECT 
    pro.clave, 
    pro.descripcion_corta_icecat AS nombre, 
    cat.nombre AS categoria,
    pro.tipo,
    pre.precio,
    pre.idMoneda AS moneda
FROM productos pro
JOIN existencias e 
    ON pro.idProductos = e.idProductos
JOIN precio pre 
    ON pro.idProductos = pre.idProducto
JOIN categorias cat 
    ON pro.idCategoria = cat.idCategoria
WHERE pro.idProductos > 0
    AND pro.activo = 1
    AND pro.tipo IN ('Memoria USB 64 GB', 'Memorias USB')
    AND pre.listaPrecio = 2
GROUP BY pro.clave
ORDER BY precio_mxn ASC;  
	
SELECT *
FROM monedas_api ;


