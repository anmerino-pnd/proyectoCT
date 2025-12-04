SELECT 
    pre.precio 			       AS precio_regular,
    pros.importe                       AS precio_oferta,
    pros.porcentaje                    AS descuento,
    pros.EnCompraDE,
    pros.Unidades, 
    pros.limitadoA, 
    pros.ProductosGratis,
    pros.fecha_inicio,
    pros.fecha_fin,
    pre.idMoneda                       AS moneda
FROM promociones pros
  INNER JOIN productos pro  
    ON pro.idProductos = pros.idProducto
  LEFT JOIN precio pre 
    ON pros.idProducto = pre.idProducto
    AND pre.listaPrecio = 2
WHERE 
    pros.fecha_fin    >= CURRENT_DATE
    AND pros.fecha_inicio <= CURRENT_DATE
    AND pro.descripcion_corta_icecat != ''
    AND pre.idMoneda IS NOT NULL
    AND pros.producto = 'MONBLR370'
    AND pros.sucursal_promo = 2
    
ORDER BY 
    pros.fecha_inicio DESC;

SELECT *
FROM promociones
#where promociones.producto = 'MONBLR370'
ORDER BY promociones.fecha_inicio DESC