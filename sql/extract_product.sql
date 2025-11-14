SELECT 
  pro.descripcion_corta_icecat AS nombre,  
  clave,  
  cat.nombre AS categoria,
  m.nombre  AS marca,
  pro.tipo, 
  pro.modelo, 
  pro.descripcion, 
  pro.descripcion_corta,
  pro.palabrasClave
FROM productos pro
LEFT JOIN categorias cat 
ON pro.idCategoria = cat.idCategoria
LEFT JOIN marcas m 
ON pro.idMarca = m.idMarca
WHERE pro.clave = 'MONBLR380'
GROUP BY pro.idProductos;