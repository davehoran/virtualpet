from rich.console import Console
from rich.table import Table
from time import sleep
import threading

# Initialize the console for Rich library
console = Console()

# Pet attributes
class VirtualPet:
    def __init__(self):
        self.happiness = 10
        self.hunger = 0
        self.health = 10
        self.cleanliness = 10
        self.running = True

    def display_stats(self):
        """Display the pet's stats in a table."""
        table = Table(title="Your Virtual Pet")
        table.add_column("Attribute", justify="center")
        table.add_column("Value", justify="center")

        table.add_row("Happiness", str(self.happiness))
        table.add_row("Hunger", str(self.hunger))
        table.add_row("Health", str(self.health))
        table.add_row("Cleanliness", str(self.cleanliness))

        console.clear()
        console.print(table)

    def degrade_stats(self):
        """Degrade the stats over time."""
        while self.running:
            sleep(5)  # Adjust time interval as needed

            # Degrade stats
            self.happiness = max(0, self.happiness - 1)
            self.hunger = min(10, self.hunger + 1)
            self.cleanliness = max(0, self.cleanliness - 1)

            # Health depends on other attributes
            if self.hunger >= 7 or self.cleanliness <= 3:
                self.health = max(0, self.health - 1)

            self.display_stats()

    def interact(self, action):
        """Perform an action to modify pet's attributes."""
        if action == "feed":
            self.hunger = max(0, self.hunger - 3)
        elif action == "play":
            self.happiness = min(10, self.happiness + 2)
            self.cleanliness = max(0, self.cleanliness - 2)
        elif action == "clean":
            self.cleanliness = 10
        elif action == "heal":
            self.health = min(10, self.health + 3)

    def stop(self):
        """Stop the degradation thread."""
        self.running = False

# Main program loop
def main():
    pet = VirtualPet()

    # Start the degradation thread
    thread = threading.Thread(target=pet.degrade_stats, daemon=True)
    thread.start()

    try:
        while True:
            pet.display_stats()
            console.print("\nChoose an action: [bold green]feed[/], [bold green]play[/], [bold green]clean[/], [bold green]heal[/]", style="bold cyan")
            action = input("Action: ").strip().lower()

            if action in ["feed", "play", "clean", "heal"]:
                pet.interact(action)
            else:
                console.print("[bold red]Invalid action. Try again.[/]")

    except KeyboardInterrupt:
        console.print("\n[bold yellow]Exiting...[/]")
        pet.stop()

if __name__ == "__main__":
    main()
