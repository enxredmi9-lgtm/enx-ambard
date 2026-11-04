--!strict
-- Создаёт таблицу лидеров (leaderstats) с монетами для каждого игрока.

local Players = game:GetService("Players")

local function onPlayerAdded(player: Player)
	local leaderstats = Instance.new("Folder")
	leaderstats.Name = "leaderstats"

	local coins = Instance.new("IntValue")
	coins.Name = "Coins"
	coins.Value = 0
	coins.Parent = leaderstats

	leaderstats.Parent = player
end

Players.PlayerAdded:Connect(onPlayerAdded)
-- На случай, если игрок зашёл раньше, чем запустился скрипт.
for _, player in Players:GetPlayers() do
	onPlayerAdded(player)
end
