sourcefiles := vol_1.txt  vol_2.txt  vol_3.txt  vol_4.txt  vol_5.txt  vol_6.txt 
pandoc-latex-opts := -V lang=ru \
	-V mainfont='PT Serif' -V sansfont='PT Sans' -V monofont='PT Mono' \
	-V header-includes='\clubpenalty=10000 \widowpenalty=1000'

csv:
	test -d $@ || mkdir -p $@

csv/%.csv: txt/%.txt scripts/split_records.py | csv
	python3 scripts/split_records.py $< $@

split: $(patsubst %.txt,csv/%.csv,$(sourcefiles))

stats: split
	python3 scripts/stats.py $(patsubst %.txt,csv/%.csv,$(sourcefiles))

%.tex: %.md
	pandoc -s $(pandoc-latex-opts) -o $@ $<

%.pdf: %.tex
	xelatex $<
	xelatex $<


