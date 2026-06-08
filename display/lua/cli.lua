local home = os.getenv('HOME')
package.path = home .. '/toolbelt/display/lua/?.lua;'
  .. home .. '/toolbelt/display/lua/actions/?.lua;'
  .. package.path

local args = _cli.args or {}
for _, moduleName in ipairs({ 'core', 'geometry', 'windows', 'actions.move', 'actions.spawn' }) do
  package.loaded[moduleName] = nil
end

local offset = 1
for index, arg in ipairs(args) do
  if arg == '--' then
    offset = index + 1
    break
  end
end

local command = args[offset]

if command == 'move' then
  local action = args[offset + 1]
  return require('actions.move').run(action, args)
end

if command == 'spawn-new' then
  return require('actions.spawn').run(args[offset + 1], args[offset + 2] or '')
end

error('unknown display command: ' .. tostring(command))
