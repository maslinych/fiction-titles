sourcefiles := vol_1.txt  vol_1.txt  vol_2.txt  vol_3.txt  vol_4.txt  vol_5.txt  vol_6.txt 

csv/%.csv: txt/%.txt
	python3 scripts/split_records.py $< $@

split: $(patsubst %.txt,csv/%.csv,$(sourcefiles))
