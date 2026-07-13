import time
import pandas as pd
from HandFromMocap import SynchronizedFullHandTracker as HandTracker  
import keyboard

class HandTrackerRecorder:
    def __init__(self, tracker):
        """
        tracker : SynchronizedFullHandTracker object
        """
        self.tracker = tracker
        self.records = []

    def record(self, duration=None):
        """
        Record data.

        Parameters
        ----------
        duration : float or None
            Recording time in seconds.
            None = record until Ctrl+C.
        """

        self.records = []

        start_time = time.time()

        try:
            while True:

                data = self.tracker.get_latest_data(block=True, timeout=1)

                if data is not None:
                    self.records.append(data)

                if duration is not None:
                    if time.time() - start_time >= duration:
                        break

                if keyboard.is_pressed('q'):
                    print("\nKey 'q' pressed. Stopping reception.")
                    break
            return pd.DataFrame(self.records)
        except KeyboardInterrupt:
            print("Recording stopped by user.")
            return None

        
    def save_csv(self, filename):
        df = pd.DataFrame(self.records)
        df.to_csv(filename, index=False)
        print(f"Saved {len(df)} frames to {filename}")
        return df

    def clear(self):
        self.records.clear()


tracker = HandTracker(
    skeleton_id=0,
    hand_bone_index=1
)

tracker.start()

recorder = HandTrackerRecorder(tracker)

print("Recording...")
df = recorder.record(duration=10)     # Record for 10 seconds

if df is not None:
    recorder.save_csv("hand_motion.csv")

tracker.stop()

print(df.head())