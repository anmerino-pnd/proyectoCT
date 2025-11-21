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
    SUM(existencias.cantidad) AS existencias,
    pre.precio as precio,
    pre.idMoneda,
    CASE WHEN EXISTS(SELECT 1 FROM promociones WHERE producto = pro.clave) 
            THEN 'Sí' ELSE 'No' END AS en_promocion
FROM productos pro
JOIN existencias e 
    ON pro.idProductos = e.idProductos
JOIN precio pre 
    ON pro.idProductos = pre.idProducto
JOIN categorias cat 
    ON pro.idCategoria = cat.idCategoria
JOIN monedas_api 
    ON pre.idMoneda = monedas_api.idMoneda
LEFT JOIN existencias
    ON pro.idProductos = existencias.idProductos
WHERE pro.idProductos > 0
    AND pro.activo = 1 
    AND pro.tipo IN ('Memoria USB 64 GB', 'Memorias USB', 'usb', 'Memoria USB')
    AND pre.listaPrecio = 2
GROUP BY pro.clave
ORDER BY (pre.precio * monedas_api.filtro) ASC
limit 10;  
	
select *
from productos
where clave = 'MEMDAH090' ;


