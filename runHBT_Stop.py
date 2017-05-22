with open(r"C:\Users\Confocal\Desktop\g2data.csv", 'w', newline='') as csvfile:
	g2writer = csv.writer(csvfile)
	g2writer.writerows([timeRow,coin.getData()])		
# Plot, stop and clear
plt.plot(coin.getData())
plt.show()
#coin.stop()
#coin.clear()