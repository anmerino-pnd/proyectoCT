SELECT 
    pro.descripcion_corta_icecat AS nombre,  
    pros.producto                      AS clave,  
    cat.nombre                        AS categoria,
    m.nombre                          AS marca,
    pro.tipo, 
    pro.modelo, 
    pro.descripcion, 
    pro.descripcion_corta,
    pro.palabrasClave
FROM promociones pros
  INNER JOIN productos pro  
    ON pro.idProductos = pros.idProducto
  LEFT JOIN precio pre 
    ON pros.idProducto = pre.idProducto
  LEFT JOIN categorias cat 
    ON pro.idCategoria = cat.idCategoria
  LEFT JOIN marcas m 
    ON pro.idMarca = m.idMarca
WHERE 
    -- promoción activa 
    pros.fecha_fin    >= CURRENT_DATE

    -- más validaciones
    AND pro.descripcion_corta_icecat != ''
    AND pre.idMoneda IS NOT NULL

GROUP BY 
    pros.idProducto 
ORDER BY 
    pros.importe     ASC,
    pre.listaPrecio;