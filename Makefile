sourcefiles := vol_1.txt  vol_2.txt  vol_3.txt  vol_4.txt  vol_5.txt  vol_6.txt 
tex-header := latex_header_ru.tex

csv:
	test -d $@ || mkdir -p $@

csv/%.csv: txt/%.txt scripts/split_records.py | csv
	python3 scripts/split_records.py $< $@

split: $(patsubst %.txt,csv/%.csv,$(sourcefiles))

stats: split
	python3 scripts/stats.py $(patsubst %.txt,csv/%.csv,$(sourcefiles))

%.tex: %.md $(tex-header)
	pandoc -s -H $(tex-header) -o $@ $<

%.pdf: %.tex
	pdflatex $<
	pdflatex $<


