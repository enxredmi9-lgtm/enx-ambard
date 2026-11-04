--!strict
-- Спавнит монеты на карте. Игрок касается монеты -> получает очки,
-- монета исчезает и появляется снова через Config.RespawnSeconds.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Config = require(ReplicatedStorage.Shared.Config)
local CoinCollected = ReplicatedStorage.Remotes.CoinCollected :: RemoteEvent

local coinsFolder = Instance.new("Folder")
coinsFolder.Name = "Coins"
coinsFolder.Parent = workspace

local random = Random.new()

local function randomPosition(): Vector3
	local angle = random:NextNumber(0, math.pi * 2)
	local distance = random:NextNumber(0, Config.SpawnRadius)
	return Vector3.new(math.cos(angle) * distance, Config.SpawnHeight, math.sin(angle) * distance)
end

local function createCoin(): Part
	local coin = Instance.new("Part")
	coin.Name = "Coin"
	coin.Shape = Enum.PartType.Cylinder
	coin.Size = Vector3.new(0.4, 2.5, 2.5)
	coin.Material = Enum.Material.Neon
	coin.Color = Color3.fromRGB(255, 200, 40)
	coin.Anchored = true
	coin.CanCollide = false
	-- Цилиндр лежит по оси X — ставим монету «на ребро».
	coin.CFrame = CFrame.new(randomPosition()) * CFrame.Angles(0, 0, math.rad(90))
	coin.Parent = coinsFolder
	return coin
end

local function spawnCoin()
	local coin = createCoin()
	local collected = false

	coin.Touched:Connect(function(hit: BasePart)
		if collected then
			return
		end
		local character = hit:FindFirstAncestorOfClass("Model")
		local player = character and Players:GetPlayerFromCharacter(character)
		if not player then
			return
		end

		local leaderstats = player:FindFirstChild("leaderstats")
		local coins = leaderstats and leaderstats:FindFirstChild("Coins") :: IntValue?
		if not coins then
			return
		end

		collected = true
		coins.Value += Config.CoinValue
		CoinCollected:FireClient(player, Config.CoinValue, coin.Position)
		coin:Destroy()

		task.delay(Config.RespawnSeconds, spawnCoin)
	end)
end

for _ = 1, Config.CoinCount do
	spawnCoin()
end
