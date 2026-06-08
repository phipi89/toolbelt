local geometry = {}

function geometry.close(a, b, tolerance)
  return math.abs(a - b) <= (tolerance or 8)
end

function geometry.sameFrame(a, b, tolerance)
  return geometry.close(a.x, b.x, tolerance)
    and geometry.close(a.y, b.y, tolerance)
    and geometry.close(a.w, b.w, tolerance)
    and geometry.close(a.h, b.h, tolerance)
end

function geometry.center(rect)
  return { x = rect.x + rect.w / 2, y = rect.y + rect.h / 2 }
end

function geometry.dist2(a, b)
  local dx, dy = a.x - b.x, a.y - b.y
  return dx * dx + dy * dy
end

function geometry.clamp(value, minValue, maxValue)
  if value < minValue then return minValue end
  if value > maxValue then return maxValue end
  return value
end

function geometry.halves(screen)
  local sf = screen:frame()
  return {
    left = hs.geometry.rect(sf.x, sf.y, sf.w / 2, sf.h),
    right = hs.geometry.rect(sf.x + sf.w / 2, sf.y, sf.w / 2, sf.h),
  }
end

function geometry.thirds(screen)
  local sf = screen:frame()
  return {
    leftTwoThirds = hs.geometry.rect(sf.x, sf.y, sf.w * 2 / 3, sf.h),
    rightOneThird = hs.geometry.rect(sf.x + sf.w * 2 / 3, sf.y, sf.w / 3, sf.h),
  }
end

function geometry.quads(screen)
  local sf = screen:frame()
  local hw, hh = sf.w / 2, sf.h / 2
  return {
    hs.geometry.rect(sf.x,      sf.y,      hw, hh),
    hs.geometry.rect(sf.x + hw, sf.y,      hw, hh),
    hs.geometry.rect(sf.x,      sf.y + hh, hw, hh),
    hs.geometry.rect(sf.x + hw, sf.y + hh, hw, hh),
  }
end

function geometry.centered(screen, scale)
  local sf = screen:frame()
  return hs.geometry.rect(
    sf.x + sf.w * (1 - scale) / 2,
    sf.y + sf.h * (1 - scale) / 2,
    sf.w * scale,
    sf.h * scale
  )
end

return geometry
