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

SELECT DISTINCT 
    pro.tipo,
    pro.busqueda
FROM productos pro
JOIN existencias e ON pro.idProductos = e.idProductos
JOIN precio pre ON pro.idProductos = pre.idProducto
WHERE pro.activo = 1
  AND pro.tipo IS NOT NULL
  AND pro.idProductos > 0
LIMIT 200;

SELECT 
	cat.nombre,
	pro.tipo
	#GROUP_CONCAT(DISTINCT pro.busqueda SEPARATOR ' | ') as busqueda_agregada
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



