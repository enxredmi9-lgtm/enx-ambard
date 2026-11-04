--!strict
-- Клиент: вращает монеты и показывает всплывающий текст «+N» при сборе.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local TweenService = game:GetService("TweenService")

local CoinCollected = ReplicatedStorage.Remotes.CoinCollected :: RemoteEvent
local player = Players.LocalPlayer

-- Вращение монет (только визуально, на клиенте).
local coinsFolder = workspace:WaitForChild("Coins")
local SPIN_SPEED = math.rad(120) -- градусов в секунду

RunService.RenderStepped:Connect(function(dt: number)
	for _, coin in coinsFolder:GetChildren() do
		if coin:IsA("BasePart") then
			coin.CFrame = coin.CFrame * CFrame.Angles(SPIN_SPEED * dt, 0, 0)
		end
	end
end)

-- Всплывающий текст.
local screenGui = Instance.new("ScreenGui")
screenGui.Name = "CoinPopups"
screenGui.ResetOnSpawn = false
screenGui.Parent = player:WaitForChild("PlayerGui")

CoinCollected.OnClientEvent:Connect(function(value: number, _position: Vector3)
	local label = Instance.new("TextLabel")
	label.AnchorPoint = Vector2.new(0.5, 0.5)
	label.Position = UDim2.fromScale(0.5, 0.45)
	label.Size = UDim2.fromOffset(200, 50)
	label.BackgroundTransparency = 1
	label.Font = Enum.Font.GothamBold
	label.TextScaled = true
	label.TextColor3 = Color3.fromRGB(255, 210, 60)
	label.TextStrokeTransparency = 0.3
	label.Text = "+" .. value
	label.Parent = screenGui

	local tween = TweenService:Create(label, TweenInfo.new(0.8, Enum.EasingStyle.Quad, Enum.EasingDirection.Out), {
		Position = UDim2.fromScale(0.5, 0.35),
		TextTransparency = 1,
		TextStrokeTransparency = 1,
	})
	tween.Completed:Connect(function()
		label:Destroy()
	end)
	tween:Play()
end)
