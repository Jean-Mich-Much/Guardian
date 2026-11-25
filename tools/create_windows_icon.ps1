$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Drawing

$root = Split-Path -Parent $PSScriptRoot
$assetDirectory = Join-Path $root "assets"
New-Item -ItemType Directory -Force -Path $assetDirectory | Out-Null
$iconPath = Join-Path $assetDirectory "guardian.ico"

$size = 256
$bitmap = [System.Drawing.Bitmap]::new(
    $size,
    $size,
    [System.Drawing.Imaging.PixelFormat]::Format32bppArgb
)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$graphics.Clear([System.Drawing.Color]::Transparent)

$background = [System.Drawing.Drawing2D.GraphicsPath]::new()
$background.AddArc(12, 12, 232, 232, 180, 90)
$background.AddArc(12, 12, 232, 232, 270, 90)
$background.AddArc(12, 12, 232, 232, 0, 90)
$background.AddArc(12, 12, 232, 232, 90, 90)
$background.CloseFigure()
$graphics.FillPath(
    [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(36, 107, 254)),
    $background
)

$flame = [System.Drawing.Point[]]@(
    [System.Drawing.Point]::new(105, 176),
    [System.Drawing.Point]::new(128, 239),
    [System.Drawing.Point]::new(151, 176),
    [System.Drawing.Point]::new(140, 188),
    [System.Drawing.Point]::new(128, 166),
    [System.Drawing.Point]::new(116, 188)
)
$graphics.FillPolygon(
    [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(255, 164, 54)),
    $flame
)
$innerFlame = [System.Drawing.Point[]]@(
    [System.Drawing.Point]::new(119, 190),
    [System.Drawing.Point]::new(128, 222),
    [System.Drawing.Point]::new(137, 190),
    [System.Drawing.Point]::new(128, 199)
)
$graphics.FillPolygon(
    [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(255, 224, 112)),
    $innerFlame
)

$rocket = [System.Drawing.Point[]]@(
    [System.Drawing.Point]::new(128, 30),
    [System.Drawing.Point]::new(171, 97),
    [System.Drawing.Point]::new(171, 155),
    [System.Drawing.Point]::new(128, 197),
    [System.Drawing.Point]::new(85, 155),
    [System.Drawing.Point]::new(85, 97)
)
$graphics.FillPolygon(
    [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(250, 252, 255)),
    $rocket
)

$leftFin = [System.Drawing.Point[]]@(
    [System.Drawing.Point]::new(86, 128),
    [System.Drawing.Point]::new(55, 169),
    [System.Drawing.Point]::new(100, 160)
)
$rightFin = [System.Drawing.Point[]]@(
    [System.Drawing.Point]::new(170, 128),
    [System.Drawing.Point]::new(201, 169),
    [System.Drawing.Point]::new(156, 160)
)
$finBrush = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(255, 164, 54))
$graphics.FillPolygon($finBrush, $leftFin)
$graphics.FillPolygon($finBrush, $rightFin)

$graphics.FillEllipse(
    [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(36, 107, 254)),
    108,
    85,
    40,
    40
)
$graphics.DrawEllipse(
    [System.Drawing.Pen]::new([System.Drawing.Color]::FromArgb(190, 219, 255), 5),
    108,
    85,
    40,
    40
)

$pngStream = [System.IO.MemoryStream]::new()
$bitmap.Save($pngStream, [System.Drawing.Imaging.ImageFormat]::Png)
$pngBytes = $pngStream.ToArray()

$iconStream = [System.IO.File]::Create($iconPath)
$writer = [System.IO.BinaryWriter]::new($iconStream)
$writer.Write([UInt16]0)
$writer.Write([UInt16]1)
$writer.Write([UInt16]1)
$writer.Write([Byte]0)
$writer.Write([Byte]0)
$writer.Write([Byte]0)
$writer.Write([Byte]0)
$writer.Write([UInt16]1)
$writer.Write([UInt16]32)
$writer.Write([UInt32]$pngBytes.Length)
$writer.Write([UInt32]22)
$writer.Write($pngBytes)
$writer.Dispose()
$pngStream.Dispose()
$graphics.Dispose()
$bitmap.Dispose()
$background.Dispose()

Write-Host "Icône Guardian créée : $iconPath"
