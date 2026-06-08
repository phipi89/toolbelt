local core = {}

function core.log(namespace, msg)
  print(os.date('[%Y-%m-%d %H:%M:%S] [' .. namespace .. '] ') .. tostring(msg))
end

function core.contains(values, target)
  if not values then return false end
  for _, value in ipairs(values) do
    if value == target then return true end
  end
  return false
end

function core.flag(args, name)
  for _, arg in ipairs(args or {}) do
    if arg == name then return true end
  end
  return false
end

function core.option(args, name)
  args = args or {}
  for i, arg in ipairs(args) do
    if arg == name then return args[i + 1] end
  end
  return nil
end

return core
