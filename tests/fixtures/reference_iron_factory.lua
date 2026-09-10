-- reference-iron-v1: deterministic test setup, not an agent trajectory.
-- Run only on the dedicated reference instance. Native machines do all work
-- after five bootstrap coal enter the boiler; no items/energy are injected later.
local s = game.surfaces[1]
game.tick_paused = true
local area = {{-30, -20}, {35, 25}}
for _, e in pairs(s.find_entities_filtered{area=area}) do
    if e.type ~= 'character' then e.destroy() end
end
local tiles = {}
for x=-30,35 do for y=-20,25 do
    tiles[#tiles+1] = {name='grass-1', position={x,y}}
end end
for x=-10,-4 do for y=7,12 do
    tiles[#tiles+1] = {name='water', position={x,y}}
end end
s.set_tiles(tiles)
local function put(name,x,y,direction)
    local e = s.create_entity{name=name,position={x,y},
        direction=direction or defines.direction.north,force='player'}
    if not e then error('Cannot place '..name..' at '..x..','..y) end
    return e
end
for _, patch in ipairs({{'coal',0.5,0.5},{'iron-ore',18.5,0.5}}) do
    for x=-2,2 do for y=-2,2 do
        s.create_entity{name=patch[1],position={patch[2]+x,patch[3]+y},amount=100000}
    end end
end
put('electric-mining-drill',0.5,0.5,defines.direction.south)
put('electric-mining-drill',18.5,0.5,defines.direction.south)
for y=2,10 do put('transport-belt',0.5,y+0.5,defines.direction.south) end
for x=0,14 do put('transport-belt',x+0.5,11.5,defines.direction.east) end
for y=8,11 do put('transport-belt',15.5,y+0.5,defines.direction.north) end
for y=2,5 do put('transport-belt',18.5,y+0.5,defines.direction.south) end
put('inserter',18.5,6.5,defines.direction.north)
put('stone-furnace',18,8)
put('inserter',16.5,8.5,defines.direction.west)
put('inserter',18.5,9.5,defines.direction.north)
put('iron-chest',18.5,10.5)
put('boiler',4.5,9).insert{name='coal',count=5}
put('inserter',4.5,10.5,defines.direction.south)
put('steam-engine',4.5,4.5)
put('pipe',4.5,7.5)
put('offshore-pump',-3.5,9.5,defines.direction.west)
for x=-3,2 do put('pipe',x+0.5,9.5) end
for _, pos in ipairs({{2.5,0.5},{8.5,0.5},{14.5,0.5},{21.5,0.5},
                      {8.5,6.5},{14.5,6.5},{21.5,6.5},{7.5,11.5}}) do
    put('medium-electric-pole',pos[1],pos[2])
end
rcon.print(helpers.table_to_json({fixture='reference-iron-v1',
    depot={x=18.5,y=10.5},bootstrap_coal=5,tick=game.tick}))
